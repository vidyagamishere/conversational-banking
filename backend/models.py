from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum


class AccountType(str, Enum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"


class OperationType(str, Enum):
    WITHDRAW = "WITHDRAW"
    DEPOSIT = "DEPOSIT"
    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"
    BALANCE_INQUIRY = "BALANCE_INQUIRY"


class IntentStatus(str, Enum):
    PENDING_DETAILS = "PENDING_DETAILS"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    LOCKED = "LOCKED"


class ReceiptMode(str, Enum):
    PRINT = "PRINT"
    EMAIL = "EMAIL"
    NONE = "NONE"


class MessageSender(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


# Customer Model
class Customer(SQLModel, table=True):
    __tablename__ = "customers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    primary_email: str
    preferred_language: str = Field(default="en")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    accounts: List["Account"] = Relationship(back_populates="customer")
    sessions: List["Session"] = Relationship(back_populates="customer")


# Account Model
class Account(SQLModel, table=True):
    __tablename__ = "accounts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    type: AccountType
    currency: str = Field(default="USD")
    balance: float = Field(default=0.0)
    status: str = Field(default="ACTIVE")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    customer: Customer = Relationship(back_populates="accounts")
    transactions_from: List["Transaction"] = Relationship(
        back_populates="from_account",
        sa_relationship_kwargs={"foreign_keys": "Transaction.from_account_id"}
    )
    transactions_to: List["Transaction"] = Relationship(
        back_populates="to_account",
        sa_relationship_kwargs={"foreign_keys": "Transaction.to_account_id"}
    )


# Session Model
class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    card_number: str
    pin_attempts: int = Field(default=0)
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    channel: str = Field(default="web")
    jwt_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    
    # Relationships
    customer: Customer = Relationship(back_populates="sessions")
    transaction_intents: List["TransactionIntent"] = Relationship(back_populates="session")
    conversation_messages: List["ConversationMessage"] = Relationship(back_populates="session")


# TransactionIntent Model
class TransactionIntent(SQLModel, table=True):
    __tablename__ = "transaction_intents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id")
    operation: OperationType
    from_account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    to_account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    amount: Optional[float] = None
    currency: str = Field(default="USD")
    receipt_preference: ReceiptMode = Field(default=ReceiptMode.NONE)
    status: IntentStatus = Field(default=IntentStatus.PENDING_DETAILS)
    missing_fields: Optional[str] = None  # JSON string
    context: Optional[str] = None  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    session: Session = Relationship(back_populates="transaction_intents")
    transactions: List["Transaction"] = Relationship(back_populates="intent")
    screen_flows: List["ScreenFlow"] = Relationship(back_populates="intent")


# Transaction Model
class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    intent_id: Optional[int] = Field(default=None, foreign_key="transaction_intents.id")
    operation: OperationType
    from_account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    to_account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    amount: float
    currency: str = Field(default="USD")
    status: TransactionStatus = Field(default=TransactionStatus.PENDING)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[str] = None  # JSON string - renamed from metadata
    
    # Relationships
    intent: Optional[TransactionIntent] = Relationship(back_populates="transactions")
    from_account: Optional[Account] = Relationship(
        back_populates="transactions_from",
        sa_relationship_kwargs={"foreign_keys": "Transaction.from_account_id"}
    )
    to_account: Optional[Account] = Relationship(
        back_populates="transactions_to",
        sa_relationship_kwargs={"foreign_keys": "Transaction.to_account_id"}
    )
    receipts: List["Receipt"] = Relationship(back_populates="transaction")


# Receipt Model
class Receipt(SQLModel, table=True):
    __tablename__ = "receipts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id")
    mode: ReceiptMode
    email: Optional[str] = None
    content: Optional[str] = None  # JSON string with formatted receipt
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    transaction: Transaction = Relationship(back_populates="receipts")


# ScreenFlow Model
class ScreenFlow(SQLModel, table=True):
    __tablename__ = "screen_flows"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    intent_id: int = Field(foreign_key="transaction_intents.id")
    steps: str  # JSON string
    status: str = Field(default="PENDING")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    intent: TransactionIntent = Relationship(back_populates="screen_flows")


# ConversationMessage Model
class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_messages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id")
    sender: MessageSender
    content: str
    channel: str = Field(default="web")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    message_metadata: Optional[str] = None  # JSON string - renamed from metadata
    
    # Relationships
    session: Session = Relationship(back_populates="conversation_messages")
