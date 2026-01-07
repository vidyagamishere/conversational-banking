"""Main FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import Optional
import json

from database import get_session
from models import (
    Customer, Account, Session as DBSession, Transaction,
    TransactionIntent, Receipt, ConversationMessage, ScreenFlow,
    AccountType, OperationType, IntentStatus, TransactionStatus,
    SessionStatus, ReceiptMode, MessageSender
)
from schemas import *
from auth import create_access_token, decode_access_token, get_pin_hash, verify_pin
from config import get_settings

settings = get_settings()
app = FastAPI(title="Conversational ATM Banking API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get current session from JWT
def get_current_session(
    authorization: str = Header(...),
    session: Session = Depends(get_session)
) -> DBSession:
    """Get current session from JWT token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    db_session = session.get(DBSession, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if db_session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Session expired or locked")
    
    if db_session.token_expires_at and db_session.token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Token expired")
    
    return db_session


# Auth Routes
@app.post("/auth/pin", response_model=PinAuthResponse)
def authenticate_pin(request: PinAuthRequest, session: Session = Depends(get_session)):
    """Authenticate user with card number and PIN."""
    # For demo purposes, we'll use hardcoded PIN mapping
    # In production, this would query the database
    pin_mapping = {
        "4111111111111111": ("1234", 1),  # (pin, customer_id)
        "4222222222222222": ("5678", 2)
    }
    
    if request.card_number not in pin_mapping:
        return PinAuthResponse(
            success=False,
            remaining_attempts=0,
            error="INVALID_ACCOUNT"
        )
    
    expected_pin, customer_id = pin_mapping[request.card_number]
    
    # Check for existing session
    existing_session = session.exec(
        select(DBSession).where(
            DBSession.card_number == request.card_number,
            DBSession.status == SessionStatus.ACTIVE
        )
    ).first()
    
    if existing_session and existing_session.status == SessionStatus.LOCKED:
        return PinAuthResponse(
            success=False,
            remaining_attempts=0,
            error="ACCOUNT_LOCKED"
        )
    
    # Verify PIN
    if request.pin != expected_pin:
        if existing_session:
            existing_session.pin_attempts += 1
            if existing_session.pin_attempts >= settings.pin_max_attempts:
                existing_session.status = SessionStatus.LOCKED
                session.commit()
                return PinAuthResponse(
                    success=False,
                    remaining_attempts=0,
                    error="ACCOUNT_LOCKED"
                )
            session.commit()
            return PinAuthResponse(
                success=False,
                remaining_attempts=settings.pin_max_attempts - existing_session.pin_attempts,
                error="INVALID_PIN"
            )
        else:
            # Create session for tracking attempts
            new_session = DBSession(
                customer_id=customer_id,
                card_number=request.card_number,
                pin_attempts=1,
                status=SessionStatus.ACTIVE,
                channel="web",
                expires_at=datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
            )
            session.add(new_session)
            session.commit()
            return PinAuthResponse(
                success=False,
                remaining_attempts=settings.pin_max_attempts - 1,
                error="INVALID_PIN"
            )
    
    # Successful authentication
    if existing_session:
        existing_session.pin_attempts = 0
        db_session = existing_session
    else:
        db_session = DBSession(
            customer_id=customer_id,
            card_number=request.card_number,
            pin_attempts=0,
            status=SessionStatus.ACTIVE,
            channel="web",
            expires_at=datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
        )
        session.add(db_session)
        session.commit()
        session.refresh(db_session)
    
    # Create JWT token
    token, expires_at = create_access_token(
        data={"session_id": db_session.id, "customer_id": customer_id}
    )
    
    db_session.jwt_token = token
    db_session.token_expires_at = expires_at
    session.commit()
    
    return PinAuthResponse(
        success=True,
        session_id=db_session.id,
        customer_id=customer_id,
        jwt_token=token,
        remaining_attempts=settings.pin_max_attempts
    )


# New API Endpoints Following Sample Request-Response Format

@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
    """
    Login Phase - Authenticate card and get enabled transactions.
    Corresponds to Section 1 in SampleRequest-Response.
    """
    # Extract card number from Track2 data
    track2_parts = request.ConsumerIdentificationData.Track2.split("=")
    card_number = track2_parts[0] if track2_parts else ""
    
    # Validate card exists (simplified for demo)
    if not card_number or len(card_number) < 10:
        raise HTTPException(status_code=400, detail="Invalid card data")
    
    return LoginResponse(
        ResponseCode="00",
        EnabledTransactions=["Withdrawal", "BalanceInquiry"],
        ConsumerGroup="Retail",
        ExtendedTransactionResponseCode="00",
        CardDataElementEntitlements=["PIN", "FastCash"],
        CardProductProperties=CardProductProperties(
            MinPinLength=4,
            MaxPinLength=6,
            FastSupported=True,
            FastCashAmount=100
        ),
        TransactionsSupported=["Withdrawal", "BalanceInquiry", "MiniStatement"]
    )


@app.post("/preferences", response_model=PreferencesResponse)
def set_preferences(request: PreferencesRequest, session: Session = Depends(get_session)):
    """
    Preferences Phase - Set user preferences including language, email, and receipt options.
    Corresponds to Section 2 in SampleRequest-Response.
    """
    # Store preferences in session (simplified for demo)
    # In production, this would update customer preferences in database
    
    return PreferencesResponse(
        AuthorizerResponseCode="00",
        AcquirerResponseCode="00",
        ActionCode="Approved",
        MessageSequenceNumber="MSG001",
        CustomerId="CUST123456",
        SessionLanguageCode=request.Preferences.Language,
        EmailAddress=request.Preferences.EmailID,
        ReceiptPreferenceCode="E" if request.Preferences.ReceiptPreference == "Email" else "P",
        FastCashTransactionAmount=100 if request.Preferences.FastCashPreference else 0,
        FastCashSourceAccountNumber="9876543210",
        FastCashSourceProductTypeCode="SAV"
    )


@app.post("/auth/pin-validation", response_model=PinValidationAccountOverviewResponse)
def pin_validation_account_overview(
    request: PinValidationAccountOverviewRequest, 
    x_session_id: Optional[str] = Header(None),
    session: Session = Depends(get_session)
):
    """
    PIN Validation + Account Overview - Validate PIN and return account information.
    Corresponds to Section 3 in SampleRequest-Response.
    """
    # In production, decrypt and validate PIN
    # For demo, we'll assume PIN is valid
    
    # Create or update database session if session ID is provided
    jwt_token = None
    if x_session_id:
        try:
            session_id = int(x_session_id)
            # Check if session already exists
            db_session = session.get(DBSession, session_id)
            
            if not db_session:
                # Create JWT token for this session
                token, expires_at = create_access_token(
                    data={"session_id": session_id, "customer_id": 1}
                )
                jwt_token = token
                
                # Create new session in database
                db_session = DBSession(
                    id=session_id,
                    customer_id=1,  # Demo customer
                    card_number="4111111111111111",  # From login
                    pin_attempts=0,
                    status=SessionStatus.ACTIVE,
                    channel="web",
                    jwt_token=token,
                    token_expires_at=expires_at,
                    expires_at=datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
                )
                session.add(db_session)
                session.commit()
            else:
                # Use existing token
                jwt_token = db_session.jwt_token
        except (ValueError, Exception) as e:
            # Invalid session ID, continue without creating session
            pass
    
    # Get customer accounts (simplified - using hardcoded data for demo)
    accounts = [
        AccountInfo(
            AccountNumber="9876543210",
            Balance=5000.0,
            Currency="USD"
        )
    ]
    
    return PinValidationAccountOverviewResponse(
        AuthorizerResponseCode="00",
        AcquirerResponseCode="00",
        ActionCode="Approved",
        MessageSequenceNumber="MSG002",
        IssuerResponseCode="00",
        PrimaryAccountNumber="9876543210",
        CptCardClassCode="CLASS1",
        TransactionMode="Online",
        Breadcrumb=request.Breadcrumb,
        ResponseCode="00",
        IntendedWkstState="Active",
        HostResponseCode="00",
        Accounts=accounts,
        SupportedTransactions=["Withdrawal", "BalanceInquiry"],
        JwtToken=jwt_token
    )


@app.post("/account-overview/finalize", response_model=AccountOverviewFinalizeResponse)
def account_overview_finalize(
    request: AccountOverviewFinalizeRequest,
    session: Session = Depends(get_session)
):
    """
    Account Overview Finalization - Finalize account overview phase.
    Corresponds to Section 4 in SampleRequest-Response.
    """
    return AccountOverviewFinalizeResponse(
        ExtendedTransactionResponseCode="00",
        ResponseCode="00",
        IntendedWkstState="Active",
        EnabledTransactions=["Withdrawal", "BalanceInquiry"]
    )


@app.post("/transactions/withdrawal/authorize", response_model=WithdrawalAuthorizeResponse)
def withdrawal_authorize(
    request: WithdrawalAuthorizeRequest,
    session: Session = Depends(get_session)
):
    """
    Withdrawal Authorization - Authorize and process withdrawal transaction.
    Corresponds to Section 5 in SampleRequest-Response.
    """
    # Validate account and balance (simplified for demo)
    source_account_number = request.SourceAccount.Number
    requested_amount = request.RequestedAmount
    
    # In production, would check actual account balance
    current_balance = 5000.0  # Demo balance
    
    if current_balance < requested_amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    
    new_balance = current_balance - requested_amount
    
    return WithdrawalAuthorizeResponse(
        AuthorizerResponseCode="00",
        AcquirerResponseCode="00",
        ActionCode="Approved",
        MessageSequenceNumber="MSG003",
        CptCardClassCode="CLASS1",
        TransactionMode="Online",
        TransactionAmount=requested_amount,
        Currency=request.Currency,
        FractionDigits=2,
        DebitedAccount=DebitedAccountData(
            AccountNumber=source_account_number,
            AccountType=request.SourceAccount.Type,
            Subtype=request.SourceAccount.Subtype
        ),
        WithdrawalDailyLimits=WithdrawalDailyLimitsData(
            Amount=500.0,
            CurrencyCode="USD",
            FractionDigits=2
        ),
        ResponseCode="00",
        EnabledTransactions=["Withdrawal", "BalanceInquiry"],
        EmvAuthorizeResponseData=EmvAuthorizeResponseData(
            Tag57="value",
            Tag5FA="value"
        ),
        AccountInformation=AccountInformationData(
            Balance=new_balance,
            CurrencyCode="USD",
            FractionDigits=2
        ),
        PossibleLimits=["DailyLimit", "PerTransactionLimit"]
    )


# Account Routes
@app.get("/accounts/summary", response_model=AccountsResponse)
def get_accounts_summary(
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Get summary of all accounts for the authenticated user."""
    accounts = session.exec(
        select(Account).where(Account.customer_id == current_session.customer_id)
    ).all()
    
    return AccountsResponse(
        accounts=[
            AccountSummary(
                account_id=acc.id,
                type=acc.type,
                currency=acc.currency,
                balance=acc.balance
            )
            for acc in accounts
        ]
    )


@app.get("/accounts/{account_id}/details", response_model=AccountDetailsResponse)
def get_account_details(
    account_id: int,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Get detailed information for a specific account."""
    account = session.get(Account, account_id)
    
    if not account or account.customer_id != current_session.customer_id:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get recent transactions
    transactions = session.exec(
        select(Transaction).where(
            (Transaction.from_account_id == account_id) | 
            (Transaction.to_account_id == account_id)
        ).order_by(Transaction.timestamp.desc()).limit(10)
    ).all()
    
    return AccountDetailsResponse(
        account_id=account.id,
        type=account.type,
        currency=account.currency,
        balance=account.balance,
        transactions=[
            TransactionDetail(
                transaction_id=txn.id,
                operation=txn.operation,
                amount=txn.amount,
                currency=txn.currency,
                timestamp=txn.timestamp,
                description=json.loads(txn.details).get("description", "") if txn.details else ""
            )
            for txn in transactions
        ]
    )


# Transaction Routes
@app.post("/transactions/withdraw", response_model=TransactionResponse)
def withdraw(
    request: TransactionRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Withdraw money from an account."""
    if not request.from_account_id:
        return TransactionResponse(success=False, error="INVALID_ACCOUNT")
    
    account = session.get(Account, request.from_account_id)
    
    if not account or account.customer_id != current_session.customer_id:
        return TransactionResponse(success=False, error="INVALID_ACCOUNT")
    
    if account.balance < request.amount:
        return TransactionResponse(success=False, error="INSUFFICIENT_FUNDS")
    
    # Process transaction
    account.balance -= request.amount
    
    transaction = Transaction(
        operation=OperationType.WITHDRAW,
        from_account_id=account.id,
        to_account_id=None,
        amount=request.amount,
        currency=request.currency,
        status=TransactionStatus.COMPLETED,
        timestamp=datetime.utcnow(),
        details=json.dumps({"description": "ATM withdrawal"})
    )
    
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    return TransactionResponse(
        success=True,
        transaction={
            "transaction_id": transaction.id,
            "operation": transaction.operation,
            "from_account_id": transaction.from_account_id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "timestamp": transaction.timestamp.isoformat()
        },
        updated_balances={account.id: account.balance}
    )


@app.post("/transactions/deposit", response_model=TransactionResponse)
def deposit(
    request: TransactionRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Deposit money into an account."""
    if not request.to_account_id:
        return TransactionResponse(success=False, error="INVALID_ACCOUNT")
    
    account = session.get(Account, request.to_account_id)
    
    if not account or account.customer_id != current_session.customer_id:
        return TransactionResponse(success=False, error="INVALID_ACCOUNT")
    
    # Process transaction
    account.balance += request.amount
    
    transaction = Transaction(
        operation=OperationType.DEPOSIT,
        from_account_id=None,
        to_account_id=account.id,
        amount=request.amount,
        currency=request.currency,
        status=TransactionStatus.COMPLETED,
        timestamp=datetime.utcnow(),
        details=json.dumps({"description": "ATM deposit"})
    )
    
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    return TransactionResponse(
        success=True,
        transaction={
            "transaction_id": transaction.id,
            "operation": transaction.operation,
            "to_account_id": transaction.to_account_id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "timestamp": transaction.timestamp.isoformat()
        },
        updated_balances={account.id: account.balance}
    )


@app.post("/transactions/transfer", response_model=TransactionResponse)
def transfer(
    request: TransactionRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Transfer money between accounts."""
    if not request.from_account_id or not request.to_account_id:
        return TransactionResponse(success=False, error="INVALID_ACCOUNT")
    
    from_account = session.get(Account, request.from_account_id)
    to_account = session.get(Account, request.to_account_id)
    
    if not from_account or from_account.customer_id != current_session.customer_id:
        return TransactionResponse(success=False, error="INVALID_ACCOUNT")
    
    if not to_account or to_account.customer_id != current_session.customer_id:
        return TransactionResponse(success=False, error="INVALID_ACCOUNT")
    
    if from_account.balance < request.amount:
        return TransactionResponse(success=False, error="INSUFFICIENT_FUNDS")
    
    # Process transaction
    from_account.balance -= request.amount
    to_account.balance += request.amount
    
    transaction = Transaction(
        operation=OperationType.TRANSFER,
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        amount=request.amount,
        currency=request.currency,
        status=TransactionStatus.COMPLETED,
        timestamp=datetime.utcnow(),
        details=json.dumps({"description": "Account transfer"})
    )
    
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    return TransactionResponse(
        success=True,
        transaction={
            "transaction_id": transaction.id,
            "operation": transaction.operation,
            "from_account_id": transaction.from_account_id,
            "to_account_id": transaction.to_account_id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "timestamp": transaction.timestamp.isoformat()
        },
        updated_balances={
            from_account.id: from_account.balance,
            to_account.id: to_account.balance
        }
    )


# Conversational Channel Route
@app.post("/channels/web/chat", response_model=ChatResponse)
async def web_chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """Process conversational chat messages."""
    from orchestrator import orchestrator
    
    # Get or create session
    if request.session_id:
        # Validate session ID is within PostgreSQL INTEGER range
        if request.session_id > 2147483647 or request.session_id < 1:
            return ChatResponse(
                messages=[],
                error="Invalid session ID. Please log in again."
            )
        
        db_session = session.get(DBSession, request.session_id)
        if not db_session or db_session.status != SessionStatus.ACTIVE:
            return ChatResponse(
                messages=[],
                error="Session expired or invalid"
            )
    else:
        return ChatResponse(
            messages=[],
            error="Session ID required"
        )
    
    # Load conversation history
    history = session.exec(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == request.session_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(10)
    ).all()
    
    conversation_history = [
        {"sender": msg.sender.value, "content": msg.content}
        for msg in reversed(history)
    ]
    
    # Save user message
    user_message = ConversationMessage(
        session_id=request.session_id,
        sender=MessageSender.USER,
        content=request.message,
        channel="web"
    )
    session.add(user_message)
    session.commit()
    
    # Load customer accounts for context
    accounts = session.exec(
        select(Account).where(Account.customer_id == db_session.customer_id)
    ).all()
    
    accounts_data = [
        {
            "id": acc.id,
            "type": acc.type.value,
            "balance": float(acc.balance),
            "currency": acc.currency
        }
        for acc in accounts
    ]
    
    # Process with orchestrator
    result = await orchestrator.process_conversation(
        message=request.message,
        conversation_history=conversation_history,
        session_context={
            "session_id": request.session_id,
            "customer_id": db_session.customer_id,
            "accounts": accounts_data
        }
    )
    
    if not result.get("success"):
        return ChatResponse(
            messages=[
                ChatMessage(sender=MessageSender.USER, content=request.message),
                ChatMessage(
                    sender=MessageSender.SYSTEM,
                    content=result.get("message", "An error occurred")
                )
            ],
            error=result.get("error")
        )
    
    # Save assistant response
    assistant_message = ConversationMessage(
        session_id=request.session_id,
        sender=MessageSender.ASSISTANT,
        content=result["message"],
        channel="web"
    )
    session.add(assistant_message)
    session.commit()
    
    # Return response with flow steps if present
    response_data = {
        "messages": [
            ChatMessage(sender=MessageSender.USER, content=request.message),
            ChatMessage(sender=MessageSender.ASSISTANT, content=result["message"])
        ],
        "flow": None
    }
    
    # Add flow steps and transaction intent if present
    if "flow_steps" in result:
        response_data["flow_steps"] = result["flow_steps"]
    if "transaction_intent" in result:
        response_data["transaction_intent"] = result["transaction_intent"]
    if "message" in result:
        response_data["message"] = result["message"]
    
    return ChatResponse(**response_data)


# Receipt Routes
@app.post("/receipts", response_model=ReceiptResponse)
def create_receipt(
    request: ReceiptRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Create a receipt for a transaction."""
    transaction = session.get(Transaction, request.transaction_id)
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Generate receipt content
    receipt_html = f"""
    <html>
    <body>
        <h2>Transaction Receipt</h2>
        <p><strong>Transaction ID:</strong> {transaction.id}</p>
        <p><strong>Operation:</strong> {transaction.operation.value}</p>
        <p><strong>Amount:</strong> {transaction.amount} {transaction.currency}</p>
        <p><strong>Date:</strong> {transaction.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Status:</strong> {transaction.status.value}</p>
    </body>
    </html>
    """
    
    receipt = Receipt(
        transaction_id=transaction.id,
        mode=request.mode,
        email=request.email,
        content=receipt_html
    )
    
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    
    return ReceiptResponse(
        success=True,
        receipt_id=receipt.id,
        mode=receipt.mode
    )


@app.get("/")
def read_root():
    return {"message": "Conversational ATM Banking API", "status": "active"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.backend_port)
