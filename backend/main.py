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
