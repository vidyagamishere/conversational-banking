from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum


# Add new enums
class PayeeCategory(str, Enum):
    UTILITY = "UTILITY"
    CREDIT_CARD = "CREDIT_CARD"
    LOAN = "LOAN"
    INSURANCE = "INSURANCE"
    RENT = "RENT"
    MORTGAGE = "MORTGAGE"
    PHONE = "PHONE"
    INTERNET = "INTERNET"
    OTHER = "OTHER"

class TransactionFrequency(str, Enum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"

class CheckDepositStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    ON_HOLD = "ON_HOLD"

class ScheduledTransactionStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class AccountType(str, Enum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"


class OperationType(str, Enum):
    WITHDRAW = "WITHDRAW"
    DEPOSIT = "DEPOSIT"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CHECK_DEPOSIT = "CHECK_DEPOSIT"
    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"
    BILL_PAYMENT = "BILL_PAYMENT"
    BALANCE_INQUIRY = "BALANCE_INQUIRY"
    PIN_CHANGE = "PIN_CHANGE"

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


# Card Model - Maps card numbers to customers
class Card(SQLModel, table=True):
    __tablename__ = "cards"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    card_number: str = Field(index=True, unique=True)  # Full PAN/Track2 data
    card_number_masked: str  # e.g., ****1111
    card_type: str = Field(default="DEBIT")  # DEBIT, CREDIT, etc.
    status: str = Field(default="ACTIVE")  # ACTIVE, BLOCKED, EXPIRED
    expiry_date: Optional[str] = None  # MMYY format
    issue_date: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    customer: "Customer" = Relationship(back_populates="cards")


# Customer Model
class Customer(SQLModel, table=True):
    __tablename__ = "customers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    primary_email: str
    preferred_language: str = Field(default="en")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    pin_hash: str
    pin_change_count: int = Field(default=0)
    last_pin_change: Optional[datetime] = None
    
    # Relationships
    cards: List["Card"] = Relationship(back_populates="customer")
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
    account_name: Optional[str] = None  # User-friendly account name
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    account_number: str = Field(index=True, unique=True)
    account_number_masked: Optional[str] = None  # e.g., **** **** **** 1234
    
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
    receipt_mode: ReceiptMode = Field(default=ReceiptMode.NONE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    memo: Optional[str] = None
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
# Add 9 new model classes at the end of file:
class PinHistory(SQLModel, table=True):
    __tablename__ = "pin_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    pin_hash: str
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    changed_by: str = Field(default="SELF")
    ip_address: Optional[str] = None
    notes: Optional[str] = None

class Payee(SQLModel, table=True):
    __tablename__ = "payees"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    name: str
    nickname: Optional[str] = None
    account_number: str
    routing_number: Optional[str] = None
    category: PayeeCategory
    address: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BillPayment(SQLModel, table=True):
    __tablename__ = "bill_payments"
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id")
    payee_id: int = Field(foreign_key="payees.id")
    payment_date: datetime
    is_recurring: bool = Field(default=False)
    recurrence_frequency: Optional[TransactionFrequency] = None
    next_payment_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    memo: Optional[str] = None
    confirmation_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CheckDeposit(SQLModel, table=True):
    __tablename__ = "check_deposits"
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id")
    check_number: str
    check_date: datetime
    payer_name: str
    payer_account: Optional[str] = None
    check_image_front: Optional[str] = None  # Base64 encoded
    check_image_back: Optional[str] = None   # Base64 encoded
    endorsement_confirmed: bool = Field(default=False)
    hold_until_date: Optional[datetime] = None
    hold_reason: Optional[str] = None
    verification_status: CheckDepositStatus = Field(default=CheckDepositStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CashDeposit(SQLModel, table=True):
    __tablename__ = "cash_deposits"
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id")
    bills_100: int = Field(default=0)
    bills_50: int = Field(default=0)
    bills_20: int = Field(default=0)
    bills_10: int = Field(default=0)
    bills_5: int = Field(default=0)
    bills_1: int = Field(default=0)
    total_bills: float = Field(default=0.0)
    coins_amount: float = Field(default=0.0)
    total_amount: float
    envelope_used: bool = Field(default=False)
    verification_status: str = Field(default="VERIFIED")
    verified_amount: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ExternalAccount(SQLModel, table=True):
    __tablename__ = "external_accounts"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    nickname: str
    bank_name: str
    account_number: str
    routing_number: str
    account_type: AccountType
    is_verified: bool = Field(default=False)
    verification_method: str = Field(default="IMMEDIATE")
    daily_transfer_limit: float = Field(default=1000.0)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ScheduledTransaction(SQLModel, table=True):
    __tablename__ = "scheduled_transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    transaction_type: str  # TRANSFER or BILL_PAYMENT
    from_account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    to_account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    external_account_id: Optional[int] = Field(default=None, foreign_key="external_accounts.id")
    payee_id: Optional[int] = Field(default=None, foreign_key="payees.id")
    amount: float
    currency: str = Field(default="USD")
    scheduled_date: datetime
    is_recurring: bool = Field(default=False)
    frequency: Optional[TransactionFrequency] = None
    next_execution_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    memo: Optional[str] = None
    status: ScheduledTransactionStatus = Field(default=ScheduledTransactionStatus.PENDING)
    execution_attempts: int = Field(default=0)
    last_execution_attempt: Optional[datetime] = None
    executed_transaction_id: Optional[int] = Field(default=None, foreign_key="transactions.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TransactionLimit(SQLModel, table=True):
    __tablename__ = "transaction_limits"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    account_id: int = Field(foreign_key="accounts.id")
    limit_date: datetime
    total_withdrawals: float = Field(default=0.0)
    total_deposits: float = Field(default=0.0)
    total_transfers: float = Field(default=0.0)
    withdrawal_count: int = Field(default=0)
    deposit_count: int = Field(default=0)
    transfer_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Translation(SQLModel, table=True):
    __tablename__ = "translations"
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str
    language: str
    value: str
    category: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)