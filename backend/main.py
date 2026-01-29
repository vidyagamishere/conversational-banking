from fastapi import Body, APIRouter
from fastapi.responses import JSONResponse
from fastapi import status
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import Optional, List
from orchestrator import orchestrator
import json
import logging


from database import get_session
from models import (
    Customer, Account, Card, Session as DBSession, Transaction,
    TransactionIntent, Receipt, ConversationMessage, ScreenFlow,
    AccountType, OperationType, IntentStatus, TransactionStatus,
    SessionStatus, ReceiptMode, MessageSender
)
from schemas import *
from auth import create_access_token, decode_access_token, get_pin_hash, verify_pin
from config import get_settings

# Add new imports
from email_service import (
    send_receipt_email,
    format_withdrawal_details,
    format_cash_deposit_details,
    format_check_deposit_details,
    format_bill_payment_details,
    format_transfer_details
)
from models import (
    Card,Payee, BillPayment, CheckDeposit, CashDeposit,
    ExternalAccount, ScheduledTransaction, Translation, PinHistory,
    PayeeCategory, TransactionFrequency, CheckDepositStatus
)
from schemas import (
    PayeeCreate, PayeeResponse, PayeeUpdate,
    CashDepositRequest, CashDepositResponse,
    CheckDepositRequest, CheckDepositResponse,
    BillPaymentRequest, BillPaymentResponse,
    ExternalAccountCreate, ExternalAccountResponse,
    ScheduledTransactionCreate, ScheduledTransactionResponse,
    ChangePinRequest, ChangePinResponse,
    TranslationResponse
)
import uuid


# --- Logging Configuration ---
import sys
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
file_handler = logging.FileHandler('backend.log', mode='a')
file_handler.setFormatter(log_formatter)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = []  # Remove any default handlers
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

# Also set Uvicorn loggers to use the same handlers
for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uvicorn_logger = logging.getLogger(uvicorn_logger_name)
    uvicorn_logger.handlers = []
    uvicorn_logger.setLevel(logging.INFO)
    uvicorn_logger.addHandler(file_handler)
    uvicorn_logger.addHandler(stream_handler)

settings = get_settings()

app = FastAPI(title="Conversational ATM Banking API", version="1.0.0")

# --- PIN Change Endpoint ---
@app.post("/pin/change")
async def change_pin(
    payload: dict = Body(...)
):
    # Simulate PIN change logic (replace with real encryption/validation in production)
    # For now, always return success for demo
    response = {
        "ResponseCode": "00",
        "PinChangeStatus": "Success",
        "MinPinLength": 4,
        "MaxPinLength": 6,
        "ReceiptGenerated": True
    }
    return JSONResponse(content=response)

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

@app.get("/cards", response_model=List[CardResponse])
def get_cards(session: Session = Depends(get_session)):
    cards = session.exec(select(Card)).all()
    return [
        CardResponse(
            card_number=c.card_number,
            card_number_masked=c.card_number_masked,
            card_type=c.card_type,
            status=c.status
        ) for c in cards
    ]

# New API Endpoints Following Sample Request-Response Format

@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
    """
    Login Phase - Authenticate card and get enabled transactions.
    Corresponds to Section 1 in SampleRequest-Response.
    Uses Track2 data to identify customer and their linked accounts.
    """
    # Extract card number from Track2 data (format: PAN=YYMM...)
    track2_parts = request.ConsumerIdentificationData.Track2.split("=")
    card_number = track2_parts[0] if track2_parts else ""
    
    print(f"[Login] Received track2 data, extracted card number: {card_number[:4]}...{card_number[-4:]}")
    
    # Validate card number format
    if not card_number or len(card_number) < 10:
        print(f"[Login] Invalid card data: {card_number}")
        raise HTTPException(status_code=400, detail="Invalid card data")
    
    # Look up card in database
    card = session.exec(select(Card).where(Card.card_number == card_number)).first()
    
    if not card:
        print(f"[Login] Card not found: {card_number[:4]}...{card_number[-4:]}")
        raise HTTPException(status_code=404, detail="Card not found")
    
    if card.status != "ACTIVE":
        print(f"[Login] Card not active: {card.status}")
        raise HTTPException(status_code=403, detail=f"Card is {card.status}")
    
    # Get customer and their accounts
    customer = session.get(Customer, card.customer_id)
    if not customer:
        print(f"[Login] Customer not found for card: {card_number[:4]}...{card_number[-4:]}")
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get all accounts linked to this customer
    accounts = session.exec(select(Account).where(Account.customer_id == customer.id)).all()
    
    print(f"[Login] Card authenticated successfully")
    print(f"[Login] Customer: {customer.name} (ID: {customer.id})")
    print(f"[Login] Linked accounts: {len(accounts)}")
    for acc in accounts:
        print(f"  - {acc.type}: {acc.account_number} (Balance: {acc.balance} {acc.currency})")
    
    return LoginResponse(
        ResponseCode="00",
        ResponseMessage=f"Card authenticated for customer {customer.name}",
        PrimaryAccountNumber=card_number,
        EnabledTransactions=["Withdrawal", "BalanceInquiry", "Transfer", "BillPayment"],
        ConsumerGroup="Retail",
        ExtendedTransactionResponseCode="00",
        CardDataElementEntitlements=["PIN", "FastCash"],
        CardProductProperties=CardProductProperties(
            MinPinLength=4,
            MaxPinLength=6,
            FastSupported=True,
            FastCashAmount=100
        ),
        TransactionsSupported=["Withdrawal", "BalanceInquiry", "MiniStatement", "Transfer", "BillPayment"]
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
    x_card_number: Optional[str] = Header(None),
    session: Session = Depends(get_session)
):
    """
    PIN Validation + Account Overview - Validate PIN and return account information.
    Corresponds to Section 3 in SampleRequest-Response.
    This endpoint validates the PIN for a customer identified by their card number,
    then returns all linked accounts for that customer.
    """
    print(f"[PIN Validation] Received request with session ID: {x_session_id}")
    print(f"[PIN Validation] Card number from header: {x_card_number[:4] if x_card_number else 'None'}...{x_card_number[-4:] if x_card_number else ''}")
    
    if not x_card_number:
        raise HTTPException(status_code=400, detail="Card number required in X-Card-Number header")
    
    # Look up card
    card = session.exec(select(Card).where(Card.card_number == x_card_number)).first()
    if not card:
        print(f"[PIN Validation] Card not found: {x_card_number[:4]}...{x_card_number[-4:]}")
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Get customer
    customer = session.get(Customer, card.customer_id)
    if not customer:
        print(f"[PIN Validation] Customer not found for card")
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Validate PIN (decrypt and verify)
    # For demo, we decode base64 and extract PIN (in production, use proper HSM decryption)
    import base64
    try:
        decoded_pin = base64.b64decode(request.EncryptedPinData).decode('utf-8')
        pin = decoded_pin  # The entire decoded value is the PIN
    except Exception as e:
        print(f"[PIN Validation] Error decoding PIN: {e}")
        # Fallback: extract last 4 characters if decoding fails
        pin = request.EncryptedPinData[-4:]
    
    print(f"[PIN Validation] Validating PIN for customer: {customer.name} (ID: {customer.id})")
    
    if not verify_pin(pin, customer.pin_hash):
        print(f"[PIN Validation] Invalid PIN for customer {customer.id}")
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    print(f"[PIN Validation] PIN validated successfully")
    
    # Get all accounts linked to this customer
    accounts = session.exec(select(Account).where(Account.customer_id == customer.id)).all()
    
    print(f"[PIN Validation] Found {len(accounts)} linked accounts")
    
    account_list = [
        AccountInfo(
            id=acc.id,
            AccountNumber=acc.account_number,
            Type=acc.type.value if hasattr(acc.type, 'value') else str(acc.type),
            Balance=acc.balance,
            Currency=acc.currency,
            AccountName=acc.account_name
        )
        for acc in accounts
    ]
    
    # Create or update database session if session ID is provided
    jwt_token = None
    if x_session_id:
        try:
            session_id = int(x_session_id)
            db_session = session.get(DBSession, session_id)
            
            if not db_session:
                # Create JWT token for this session
                token, expires_at = create_access_token(
                    data={"session_id": session_id, "customer_id": customer.id}
                )
                jwt_token = token
                
                print(f"[PIN Validation] Creating new session {session_id} for customer {customer.id}")
                
                # Create new session in database
                db_session = DBSession(
                    id=session_id,
                    customer_id=customer.id,
                    card_number=x_card_number,
                    pin_attempts=0,
                    status=SessionStatus.ACTIVE,
                    channel="web",
                    jwt_token=token,
                    token_expires_at=expires_at,
                    expires_at=datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
                )
                session.add(db_session)
                session.commit()
                print(f"[PIN Validation] Session created successfully")
            else:
                # Use existing token
                jwt_token = db_session.jwt_token
                print(f"[PIN Validation] Using existing session")
        except (ValueError, Exception) as e:
            print(f"[PIN Validation] Error creating session: {e}")
            # Invalid session ID, continue without creating session
            pass
    
    return PinValidationAccountOverviewResponse(
        AuthorizerResponseCode="00",
        AcquirerResponseCode="00",
        ActionCode="Approved",
        MessageSequenceNumber="MSG002",
        IssuerResponseCode="00",
        PrimaryAccountNumber=card.card_number,
        CptCardClassCode="CLASS1",
        TransactionMode="Online",
        Breadcrumb=request.Breadcrumb,
        ResponseCode="00",
        IntendedWkstState="Active",
        HostResponseCode="00",
        Accounts=account_list,
        SupportedTransactions=["Withdrawal", "BalanceInquiry", "Transfer", "BillPayment"],
        JwtToken=jwt_token,
        CustomerName=customer.name
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
    # Validate account and balance (fetch from DB)
    source_account_number = request.SourceAccount.Number
    requested_amount = request.RequestedAmount

    # Fetch account from DB
    account = session.exec(select(Account).where(Account.account_number == source_account_number)).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    current_balance = account.balance
    if current_balance < requested_amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Deduct amount and update balance
    account.balance -= requested_amount
    session.commit()
    new_balance = account.balance

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
            CurrencyCode=account.currency,
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


@app.post("/transactions/transfer-v2", response_model=TransferV2Response, status_code=status.HTTP_200_OK)
def transfer_v2(
    request: TransferV2Request,
    session: Session = Depends(get_session),
    authorization: str = Header(None)
):
    """Process internal or external transfer with new request/response format."""
    # Find source account
    from_account = session.exec(
        select(Account).where(Account.account_number == request.SourceAccount.Number)
    ).first()
    if not from_account:
        return TransferV2Response(
            ResponseCode="01",
            TransactionAmount=request.TransferAmount,
            SourceUpdatedBalance=0,
            DestinationUpdatedBalance="INVALID_SOURCE_ACCOUNT",
            Currency=request.Currency,
            ReceiptGenerated=False
        )
    # Check sufficient funds
    if from_account.balance < request.TransferAmount:
        return TransferV2Response(
            ResponseCode="51",
            TransactionAmount=request.TransferAmount,
            SourceUpdatedBalance=from_account.balance,
            DestinationUpdatedBalance="INSUFFICIENT_FUNDS",
            Currency=request.Currency,
            ReceiptGenerated=False
        )
    # Internal or external?
    is_internal = request.DestinationAccount.Type in ("SAV", "CHK", "SAVINGS", "CHECKING")
    dest_account = None
    if is_internal:
        dest_account = session.exec(
            select(Account).where(Account.account_number == request.DestinationAccount.Number)
        ).first()
        if not dest_account:
            return TransferV2Response(
                ResponseCode="02",
                TransactionAmount=request.TransferAmount,
                SourceUpdatedBalance=from_account.balance,
                DestinationUpdatedBalance="INVALID_DEST_ACCOUNT",
                Currency=request.Currency,
                ReceiptGenerated=False
            )
    # Process transfer
    from_account.balance -= request.TransferAmount
    if is_internal:
        dest_account.balance += request.TransferAmount
        session.add(dest_account)
    session.add(from_account)
    session.commit()
    # Build response
    if is_internal:
        dest_balance = dest_account.balance
    else:
        dest_balance = "Available after processing"
    # Optionally, create a Transaction record here
    return TransferV2Response(
        ResponseCode="00",
        TransactionAmount=request.TransferAmount,
        SourceUpdatedBalance=from_account.balance,
        DestinationUpdatedBalance=str(dest_balance),
        Currency=request.Currency,
        ReceiptGenerated=True
    )
def canonical_account_type(raw_type: str | None, account_name: str | None) -> str | None:
        """
        Map DB type + account_name into canonical CHECKING / SAVINGS families.
        """
        if not raw_type:
            return None

        t = raw_type.strip().upper()
        name = (account_name or "").strip().upper()

        # Primary from DB type column (your CSV already uses CHECKING / SAVINGS).[file:53]
        if t in ["CHECKING", "SAVINGS"]:
            return t

        # Fallback from account_name if needed (for future products)
        if any(k in name for k in ["CHECKING"]):
            return "CHECKING"
        if any(k in name for k in ["SAVINGS", "MONEY MARKET", "HIGH YIELD", "HEALTH SAVINGS", "HSA"]):
            return "SAVINGS"

        return t  # fallback: unknown but still something


# Conversational Channel Route

@app.post("/channels/web/chat")
async def web_chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    # Get or create session
    if request.session_id:
        # Validate session ID is within PostgreSQL INTEGER range
        if request.session_id > 2147483647 or request.session_id < 1:
            return {"messages": [], "error": "Invalid session ID. Please log in again."}
        db_session = session.get(DBSession, request.session_id)
        if not db_session or db_session.status != SessionStatus.ACTIVE:
            return {"messages": [], "error": "Session expired or invalid"}
    else:
        return {"messages": [], "error": "Session ID required"}

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
            "type": canonical_account_type(
                acc.type.value,
                getattr(acc, "account_name", None)
            ),
            "raw_type": acc.type.value,
            "account_name": getattr(acc, "account_name", None),
            "balance": float(acc.balance),
            "currency": acc.currency,
        }
        for acc in accounts
    ]
    logging.info("accounts_data for session %s: %s", request.session_id, accounts_data)

    # Build session context with pending_intent if provided
    session_ctx = {
        "session_id": request.session_id,
        "customer_id": db_session.customer_id,
        "accounts": accounts_data
    }
    if request.pending_intent:
        session_ctx["pending_intent"] = request.pending_intent
        logging.info("[web_chat] Received pending_intent: %s", request.pending_intent)

    # Process with orchestrator
    result = await orchestrator.process_conversation(
        message=request.message,
        conversation_history=conversation_history,
        session_context=session_ctx
    )

    # Save assistant response (if message present)
    if "message" in result:
        assistant_message = ConversationMessage(
            session_id=request.session_id,
            sender=MessageSender.ASSISTANT,
            content=result["message"],
            channel="web"
        )
        session.add(assistant_message)
        session.commit()

    # Always return the orchestrator result as the API response (including clarification fields, etc.)
    return result


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

# 1. Translations
@app.get("/translations/{language}", response_model=Dict[str, str])
def get_translations(language: str, session: Session = Depends(get_session)):
    """Get all translations for a language."""
    translations = session.exec(
        select(Translation).where(Translation.language == language)
    ).all()
    
    return {t.key: t.value for t in translations}

# 2. Payees
@app.get("/payees", response_model=List[PayeeResponse])
def get_payees(
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Get all payees for current customer."""
    customer = session.get(Customer, current_session.customer_id)
    payees = session.exec(
        select(Payee).where(
            Payee.customer_id == customer.id,
            Payee.is_active == True
        )
    ).all()
    
    return payees

@app.post("/payees", response_model=PayeeResponse)
def create_payee(
    payee_data: PayeeCreate,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Create new payee."""
    payee = Payee(
        customer_id=current_session.customer_id,
        **payee_data.dict()
    )
    session.add(payee)
    session.commit()
    session.refresh(payee)
    return payee

@app.delete("/payees/{payee_id}")
def delete_payee(
    payee_id: int,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Delete payee (soft delete)."""
    payee = session.get(Payee, payee_id)
    if not payee or payee.customer_id != current_session.customer_id:
        raise HTTPException(status_code=404, detail="Payee not found")
    
    payee.is_active = False
    session.commit()
    return {"success": True, "message": "Payee deleted"}

# 3. Cash Deposit
@app.post("/transactions/cash-deposit", response_model=CashDepositResponse)
async def cash_deposit(
    request: CashDepositRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Process cash deposit with denomination breakdown."""
    logging.info(f"Cash deposit request received for account id {request.account_id}")
    account = session.get(Account, request.account_id)
    logging.info(f"Account id {request.account_id}")
    if not account or account.customer_id != current_session.customer_id:
        logging.info(f"[CASH DEPOSIT] Account not found or unauthorized for account id: {request.account_id}")
        raise HTTPException(status_code=404, detail="Account not found")
    # Calculate total
    total = (
        request.bills_100 * 100 +
        request.bills_50 * 50 +
        request.bills_20 * 20 +
        request.bills_10 * 10 +
        request.bills_5 * 5 +
        request.bills_1 * 1 +
        request.coins_amount
    )
    logging.info(f"[CASH DEPOSIT] Calculated total: {total}")
    # Update account balance
    account.balance += total
    logging.info(f"[CASH DEPOSIT] Updated account balance: {account.balance}")

    # Create transaction
    transaction = Transaction(
        operation=OperationType.CASH_DEPOSIT,
        to_account_id=account.id,
        amount=total,
        status=TransactionStatus.COMPLETED,
        receipt_mode=request.receipt_mode,
        timestamp=datetime.utcnow()
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    # Create cash deposit record
    cash_deposit_record = CashDeposit(
        transaction_id=transaction.id,
        bills_100=request.bills_100,
        bills_50=request.bills_50,
        bills_20=request.bills_20,
        bills_10=request.bills_10,
        bills_5=request.bills_5,
        bills_1=request.bills_1,
        coins_amount=request.coins_amount,
        total_bills=total - request.coins_amount,
        total_amount=total,
        envelope_used=request.envelope_used
    )
    session.add(cash_deposit_record)
    session.commit()
    logging.info(f"[CASH DEPOSIT] Cash deposit record created: {cash_deposit_record}")
    # Send email receipt if requested
    receipt_sent = False
    if request.receipt_mode == ReceiptMode.EMAIL:
        customer = session.get(Customer, current_session.customer_id)
        details = format_cash_deposit_details(
            transaction.id,
            account.account_number_masked,
            {
                "bills_100": request.bills_100,
                "bills_50": request.bills_50,
                "bills_20": request.bills_20,
                "bills_10": request.bills_10,
                "bills_5": request.bills_5,
                "bills_1": request.bills_1,
                "coins_amount": request.coins_amount
            },
            account.balance
        )
        logging.info(f"[CASH DEPOSIT] Sending email receipt to {customer.primary_email}")
        receipt_sent = await send_receipt_email(customer.primary_email, "cash_deposit", details)
        logging.info(f"[CASH DEPOSIT] Email receipt sent: {receipt_sent}")

    return CashDepositResponse(
        success=True,
        transaction_id=transaction.id,
        new_balance=account.balance,
        total_deposited=total,
        receipt_sent=receipt_sent,
        message="Cash deposit successful"
    )


@app.post("/transactions/check-deposit", response_model=CheckDepositResponse)
async def check_deposit(
    request: CheckDepositRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Process check deposit (supports multiple checks)."""
    logging.info(f"Check deposit request received for account id {request.account_id}, {len(request.checks)} check(s)")
    account = session.get(Account, request.account_id)
    logging.info(f"Account id {request.account_id}")
    if not account or account.customer_id != current_session.customer_id:
        logging.info(f"[CHECK DEPOSIT] Account not found or unauthorized for account id: {request.account_id}")
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Auto-generate check details if not provided (simulating device detection)
    import random
    from datetime import timedelta
    
    total_amount = 0.0
    check_deposit_records = []
    transaction_ids = []
    
    # Process each check
    for idx, check in enumerate(request.checks):
        check_number = check.check_number or f"CHK{random.randint(100000, 999999)}"
        check_date_str = check.check_date or datetime.utcnow().strftime("%Y-%m-%d")
        payer_name = check.payer_name or random.choice([
            "ABC Corporation",
            "XYZ Industries",
            "John Smith",
            "Jane Doe",
            "Global Services LLC",
            "Tech Solutions Inc."
        ])
        
        logging.info(f"[CHECK DEPOSIT] Check {idx+1} - Number: {check_number}, Date: {check_date_str}, Payer: {payer_name}, Amount: ${check.amount:.2f}")
        
        # Create transaction for each check
        transaction = Transaction(
            operation=OperationType.CHECK_DEPOSIT,
            to_account_id=account.id,
            amount=check.amount,
            status=TransactionStatus.COMPLETED,
            receipt_mode=request.receipt_mode,
            timestamp=datetime.utcnow()
        )
        session.add(transaction)
        session.flush()  # Get transaction ID
        
        transaction_ids.append(transaction.id)
        total_amount += check.amount
        
        # Create check deposit record with hold
        hold_days = 2  # 2 business days hold
        hold_until = datetime.utcnow() + timedelta(days=hold_days)
        check_deposit_record = CheckDeposit(
            transaction_id=transaction.id,
            check_number=check_number,
            check_date=datetime.strptime(check_date_str, "%Y-%m-%d"),
            payer_name=payer_name,
            payer_account=check.payer_account,
            check_image_front=check.check_image_front,
            check_image_back=check.check_image_back,
            endorsement_confirmed=request.endorsement_confirmed,
            hold_until_date=hold_until,
            hold_reason="Standard hold period",
            verification_status=CheckDepositStatus.PENDING
        )
        session.add(check_deposit_record)
        check_deposit_records.append(check_deposit_record)
    
    # Update account balance with total amount
    account.balance += total_amount
    logging.info(f"New account balance {account.balance} (deposited {len(request.checks)} checks totaling ${total_amount:.2f})")
    
    session.commit()
    
    # Send email receipt (for all checks combined)
    receipt_sent = False
    if request.receipt_mode == ReceiptMode.EMAIL:
        customer = session.get(Customer, current_session.customer_id)
        # Format details for all checks
        check_details_list = [
            f"  Check #{rec.check_number}: ${chk.amount:.2f} from {rec.payer_name} (dated {rec.check_date.strftime('%Y-%m-%d')})"
            for rec, chk in zip(check_deposit_records, request.checks)
        ]
        details = f"""
Transaction ID: {transaction_ids[0]} (and {len(transaction_ids)-1} more)
Account: {account.account_number_masked}
Number of Checks: {len(request.checks)}
Total Amount: ${total_amount:.2f}

Check Details:
{chr(10).join(check_details_list)}

New Balance: ${account.balance:.2f}
Hold Until: {check_deposit_records[0].hold_until_date.strftime('%B %d, %Y')}
Status: Pending Verification
"""
        logging.info(f"[CHECK DEPOSIT] Sending email receipt to {customer.primary_email}")
        receipt_sent = await send_receipt_email(customer.primary_email, "check_deposit", details)
        logging.info(f"[CHECK DEPOSIT] Email receipt sent: {receipt_sent}")

    return CheckDepositResponse(
        success=True,
        transaction_id=transaction_ids[0],  # Return first transaction ID
        check_deposit_id=check_deposit_records[0].id,
        new_balance=account.balance,
        hold_until_date=check_deposit_records[0].hold_until_date.strftime("%Y-%m-%d"),
        verification_status=CheckDepositStatus.PENDING,
        receipt_sent=receipt_sent,
        message=f"{len(request.checks)} check(s) deposited successfully (total ${total_amount:.2f}). Funds will be available after verification."
    )

# --- Updated /channels/web/chat endpoint to return orchestrator result as-is (including clarification fields) ---
@app.post("/channels/web/chat")
async def web_chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    # Get or create session
    if request.session_id:
        # Validate session ID is within PostgreSQL INTEGER range
        if request.session_id > 2147483647 or request.session_id < 1:
            return {"messages": [], "error": "Invalid session ID"}
        db_session = session.get(DBSession, request.session_id)
        if not db_session or db_session.status != SessionStatus.ACTIVE:
            return {"messages": [], "error": "Session not found or inactive"}
    else:
        return {"messages": [], "error": "Session ID required"}

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
            "type": canonical_account_type(
                acc.type.value,
                getattr(acc, "account_name", None)
            ),
            "raw_type": acc.type.value,
            "account_name": getattr(acc, "account_name", None),
            "balance": float(acc.balance),
            "currency": acc.currency,
        }
        for acc in accounts
    ]
    logging.info("accounts_data for session %s: %s", request.session_id, accounts_data)

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

    # Save assistant response (if message present)
    if "message" in result:
        assistant_message = ConversationMessage(
            session_id=request.session_id,
            sender=MessageSender.ASSISTANT,
            content=result["message"],
            channel="web"
        )
        session.add(assistant_message)
        session.commit()

    # Return the orchestrator result as the API response (including clarification fields, etc.)


# 5. Bill Payment
@app.post("/transactions/bill-payment", response_model=BillPaymentResponse)
async def bill_payment(
    request: BillPaymentRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Process bill payment."""
    account = session.get(Account, request.from_account_id)
    if not account or account.customer_id != current_session.customer_id:
        raise HTTPException(status_code=404, detail="Account not found")
    
    payee = session.get(Payee, request.payee_id)
    if not payee or payee.customer_id != current_session.customer_id:
        raise HTTPException(status_code=404, detail="Payee not found")
    
    if account.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    
    # Update account balance
    account.balance -= request.amount
    logging.info(f"New account balance {account.balance}")
    
    # Create transaction
    transaction = Transaction(
        operation=OperationType.BILL_PAYMENT,
        from_account_id=account.id,
        amount=request.amount,
        status=TransactionStatus.COMPLETED,
        receipt_mode=request.receipt_mode,
        memo=request.memo,
        timestamp=datetime.utcnow()
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    # Create bill payment record
    confirmation_num = f"BP{datetime.utcnow().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
    payment_date = datetime.strptime(request.payment_date, "%Y-%m-%d") if request.payment_date else datetime.utcnow()
    
    bill_payment_record = BillPayment(
        transaction_id=transaction.id,
        payee_id=payee.id,
        payment_date=payment_date,
        is_recurring=request.is_recurring,
        recurrence_frequency=request.recurrence_frequency,
        end_date=datetime.strptime(request.end_date, "%Y-%m-%d") if request.end_date else None,
        memo=request.memo,
        confirmation_number=confirmation_num
    )
    logging.info(f"New account balance {account.balance}")
    session.add(bill_payment_record)
    session.commit()
    
    # Send email receipt
    receipt_sent = False
    if request.receipt_mode == ReceiptMode.EMAIL:
        customer = session.get(Customer, current_session.customer_id)
        details = format_bill_payment_details(
            transaction.id,
            confirmation_num,
            account.account_number_masked,
            payee.name,
            request.amount,
            account.balance,
            request.is_recurring,
            request.recurrence_frequency.value if request.recurrence_frequency else None
        )
        receipt_sent = await send_receipt_email(customer.primary_email, "bill_payment", details)
    
    return BillPaymentResponse(
        success=True,
        transaction_id=transaction.id,
        bill_payment_id=bill_payment_record.id,
        confirmation_number=confirmation_num,
        new_balance=account.balance,
        receipt_sent=receipt_sent,
        message="Bill payment successful"
    )

# 6. External Accounts
@app.get("/accounts/external", response_model=List[ExternalAccountResponse])
def get_external_accounts(
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Get all external accounts for current customer."""
    accounts = session.exec(
        select(ExternalAccount).where(
            ExternalAccount.customer_id == current_session.customer_id,
            ExternalAccount.is_active == True
        )
    ).all()
    
    # Mask account numbers
    for acc in accounts:
        acc.account_number = f"****{acc.account_number[-4:]}"
    
    return accounts

@app.post("/accounts/external", response_model=ExternalAccountResponse)
def create_external_account(
    account_data: ExternalAccountCreate,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Add external account."""
    external_account = ExternalAccount(
        customer_id=current_session.customer_id,
        is_verified=True,  # Immediate verification
        verification_method="IMMEDIATE",
        **account_data.dict()
    )
    session.add(external_account)
    session.commit()
    session.refresh(external_account)
    
    # Mask account number for response
    external_account.account_number = f"****{external_account.account_number[-4:]}"
    return external_account

# 7. Change PIN
@app.post("/auth/change-pin", response_model=ChangePinResponse)
def change_pin(
    request: ChangePinRequest,
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Change customer PIN."""
    customer = session.get(Customer, current_session.customer_id)
    
    # Verify current PIN
    if not verify_pin(request.current_pin, customer.pin_hash):
        raise HTTPException(status_code=400, detail="Current PIN is incorrect")
    
    # Validate new PIN
    if request.new_pin != request.confirm_pin:
        raise HTTPException(status_code=400, detail="New PIN and confirmation do not match")
    
    if len(request.new_pin) < 4 or len(request.new_pin) > 6:
        raise HTTPException(status_code=400, detail="PIN must be 4-6 digits")
    
    if not request.new_pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must contain only digits")
    
    # Save old PIN to history
    pin_history = PinHistory(
        customer_id=customer.id,
        pin_hash=customer.pin_hash,
        changed_by="SELF"
    )
    session.add(pin_history)
    
    # Update customer PIN
    customer.pin_hash = get_pin_hash(request.new_pin)
    customer.pin_change_count += 1
    customer.last_pin_change = datetime.utcnow()
    session.commit()
    
    return ChangePinResponse(
        success=True,
        message="PIN changed successfully"
    )

# 8. Scheduled Transactions (simple get and execute)
@app.get("/scheduled-transactions", response_model=List[ScheduledTransactionResponse])
def get_scheduled_transactions(
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Get pending scheduled transactions for customer."""
    scheduled = session.exec(
        select(ScheduledTransaction).where(
            ScheduledTransaction.customer_id == current_session.customer_id,
            ScheduledTransaction.status == "PENDING"
        )
    ).all()
    
    return [
        ScheduledTransactionResponse(
            id=s.id,
            transaction_type=s.transaction_type,
            amount=s.amount,
            scheduled_date=s.scheduled_date.strftime("%Y-%m-%d"),
            is_recurring=s.is_recurring,
            status=s.status,
            message=f"Scheduled for {s.scheduled_date.strftime('%Y-%m-%d')}"
        )
        for s in scheduled
    ]

@app.post("/transactions/execute-scheduled")
def execute_scheduled_transactions(
    current_session: DBSession = Depends(get_current_session),
    session: Session = Depends(get_session)
):
    """Manually trigger execution of due scheduled transactions."""
    from datetime import date
    today = date.today()
    
    scheduled = session.exec(
        select(ScheduledTransaction).where(
            ScheduledTransaction.customer_id == current_session.customer_id,
            ScheduledTransaction.status == "PENDING",
            ScheduledTransaction.scheduled_date <= today
        )
    ).all()
    
    executed_count = 0
    for sched in scheduled:
        # Execute the transaction (simplified)
        # In production, this would create actual transactions
        sched.status = "EXECUTED"
        sched.execution_attempts += 1
        sched.last_execution_attempt = datetime.utcnow()
        executed_count += 1
    
    session.commit()
    
    return {
        "success": True,
        "executed_count": executed_count,
        "message": f"Executed {executed_count} scheduled transaction(s)"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.backend_port)
