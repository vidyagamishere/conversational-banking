"""Pydantic schemas for API request/response models."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from models import (
    AccountType, OperationType, IntentStatus,
    TransactionStatus, ReceiptMode, MessageSender,PayeeCategory, TransactionFrequency, CheckDepositStatus
)


# 1. Login Phase Schemas
class ConsumerIdentificationData(BaseModel):
    Track2: str
    EMVTags: List[str]
    ManualDataType: str


class LoginRequest(BaseModel):
    ClientId: str
    ClientRequestNumber: str
    ClientRequestTime: str
    ClientUniqueHardwareId: str
    ConsumerIdentificationData: ConsumerIdentificationData


class CardProductProperties(BaseModel):
    MinPinLength: int
    MaxPinLength: int
    FastSupported: bool
    FastCashAmount: float


class LoginResponse(BaseModel):
    ResponseCode: str
    ResponseMessage: Optional[str] = None
    PrimaryAccountNumber: Optional[str] = None
    EnabledTransactions: List[str]
    ConsumerGroup: str
    ExtendedTransactionResponseCode: str
    CardDataElementEntitlements: List[str]
    CardProductProperties: CardProductProperties
    TransactionsSupported: List[str]


# Card response schema for /cards endpoint
class CardResponse(BaseModel):
    card_number: str
    card_number_masked: str
    card_type: str
    status: str


# 2. Preferences Phase Schemas
class PreferencesData(BaseModel):
    Language: str
    EmailID: str
    ReceiptPreference: str
    FastCashPreference: bool


class PreferencesRequest(BaseModel):
    ClientId: str
    ClientRequestNumber: str
    ClientRequestTime: str
    ClientUniqueHardwareId: str
    CardPosition: str
    Preferences: PreferencesData


class PreferencesResponse(BaseModel):
    AuthorizerResponseCode: str
    AcquirerResponseCode: str
    ActionCode: str
    MessageSequenceNumber: str
    CustomerId: str
    SessionLanguageCode: str
    EmailAddress: str
    ReceiptPreferenceCode: str
    FastCashTransactionAmount: float
    FastCashSourceAccountNumber: str
    FastCashSourceProductTypeCode: str


# 3. PIN Validation + Account Overview Schemas
class EmvAuthorizeRequestData(BaseModel):
    Tag57: Optional[str] = None
    Tag5FA: Optional[str] = None


class PinValidationAccountOverviewRequest(BaseModel):
    ClientId: str
    ClientRequestNumber: str
    EncryptedPinData: str
    EmvAuthorizeRequestData: EmvAuthorizeRequestData
    Breadcrumb: str


class AccountInfo(BaseModel):
    id: int  # Actual account id from DB
    AccountNumber: str
    Type: str  # CHECKING, SAVINGS, etc.
    Balance: float
    Currency: str
    AccountName: Optional[str] = None


class PinValidationAccountOverviewResponse(BaseModel):
    AuthorizerResponseCode: str
    AcquirerResponseCode: str
    ActionCode: str
    MessageSequenceNumber: str
    IssuerResponseCode: str
    PrimaryAccountNumber: str
    CptCardClassCode: str
    TransactionMode: str
    Breadcrumb: str
    ResponseCode: str
    IntendedWkstState: str
    HostResponseCode: str
    Accounts: List[AccountInfo]
    SupportedTransactions: List[str]
    JwtToken: Optional[str] = None  # Added for frontend authentication
    CustomerName: Optional[str] = None  # Customer name for personalized UI
    CustomerName: Optional[str] = None  # Customer name for personalized UI


# 4. Account Overview Finalization Schemas
class EmvFinalizeRequestData(BaseModel):
    Tags: List[str]


class AccountOverviewFinalizeRequest(BaseModel):
    ClientId: str
    ClientRequestNumber: str
    ClientRequestTime: str
    ClientUniqueHardwareId: str
    CardPosition: str
    ClientTransactionResult: str
    AccountingState: str
    CardUpdateState: str
    EmvFinalizeRequestData: EmvFinalizeRequestData


class AccountOverviewFinalizeResponse(BaseModel):
    ExtendedTransactionResponseCode: str
    ResponseCode: str
    IntendedWkstState: str
    EnabledTransactions: List[str]


# 5. Withdrawal Authorization Schemas
class SourceAccountData(BaseModel):
    Number: str
    Type: str
    Subtype: str


class WithdrawalAuthorizeRequest(BaseModel):
    ClientId: str
    ClientRequestNumber: str
    ClientRequestTime: str
    ClientUniqueHardwareId: str
    CardPosition: str
    HostTransactionNumber: str
    EncryptedPinData: str
    EmvAuthorizeRequestData: EmvAuthorizeRequestData
    CardTechnology: str
    SourceAccount: SourceAccountData
    RequestedAmount: float
    Currency: str


class DebitedAccountData(BaseModel):
    AccountNumber: str
    AccountType: str
    Subtype: str


class WithdrawalDailyLimitsData(BaseModel):
    Amount: float
    CurrencyCode: str
    FractionDigits: int


class EmvAuthorizeResponseData(BaseModel):
    Tag57: Optional[str] = None
    Tag5FA: Optional[str] = None


class AccountInformationData(BaseModel):
    Balance: float
    CurrencyCode: str
    FractionDigits: int


class WithdrawalAuthorizeResponse(BaseModel):
    AuthorizerResponseCode: str
    AcquirerResponseCode: str
    ActionCode: str
    MessageSequenceNumber: str
    CptCardClassCode: str
    TransactionMode: str
    TransactionAmount: float
    Currency: str
    FractionDigits: int
    DebitedAccount: DebitedAccountData
    WithdrawalDailyLimits: WithdrawalDailyLimitsData
    ResponseCode: str
    EnabledTransactions: List[str]
    EmvAuthorizeResponseData: EmvAuthorizeResponseData
    AccountInformation: AccountInformationData
    PossibleLimits: List[str]


# Legacy Auth Schemas (keeping for backward compatibility)
class PinAuthRequest(BaseModel):
    card_number: str
    pin: str


class PinAuthResponse(BaseModel):
    success: bool
    session_id: Optional[int] = None
    customer_id: Optional[int] = None
    jwt_token: Optional[str] = None
    remaining_attempts: int
    error: Optional[str] = None


# Account Schemas
class AccountSummary(BaseModel):
    account_id: int
    type: AccountType
    currency: str
    balance: float


class AccountsResponse(BaseModel):
    accounts: List[AccountSummary]


class TransactionDetail(BaseModel):
    transaction_id: int
    operation: OperationType
    amount: float
    currency: str
    timestamp: datetime
    description: str


class AccountDetailsResponse(BaseModel):
    account_id: int
    type: AccountType
    currency: str
    balance: float
    transactions: List[TransactionDetail]


# Intent Schemas
class ConversationalIntentRequest(BaseModel):
    session_id: int
    natural_language_request: str


class IntentResponse(BaseModel):
    intent_id: int
    operation: OperationType
    status: IntentStatus
    from_account_id: Optional[int] = None
    to_account_id: Optional[int] = None
    amount: Optional[float] = None
    currency: str = "USD"
    receipt_preference: ReceiptMode = ReceiptMode.NONE
    missing_fields: List[str] = []
    clarification_questions: List[str] = []


class IntentUpdateRequest(BaseModel):
    session_id: int
    answers: Dict[str, Any]


class IntentUpdateResponse(BaseModel):
    intent_id: int
    status: IntentStatus
    missing_fields: List[str]
    summary: Optional[Dict[str, Any]] = None


# Transaction Schemas
class TransactionExecuteRequest(BaseModel):
    session_id: int
    intent_id: int


class TransactionResponse(BaseModel):
    success: bool
    transaction: Optional[Dict[str, Any]] = None
    updated_balances: Optional[Dict[int, float]] = None
    error: Optional[str] = None


class TransactionRequest(BaseModel):
    session_id: int
    from_account_id: Optional[int] = None
    to_account_id: Optional[int] = None
    amount: float
    currency: str = "USD"
    receipt_preference: ReceiptMode = ReceiptMode.NONE


# Flow Schemas
class FlowStep(BaseModel):
    id: str
    label: str
    screen_type: str


class FlowResponse(BaseModel):
    flow_id: int
    intent_id: int
    steps: List[FlowStep]


class FlowInterruptRequest(BaseModel):
    session_id: int


class FlowInterruptResponse(BaseModel):
    flow_id: int
    status: str
    intent: Optional[Dict[str, Any]] = None


# Receipt Schemas
class ReceiptRequest(BaseModel):
    session_id: int
    transaction_id: int
    mode: ReceiptMode
    email: Optional[str] = None


class ReceiptResponse(BaseModel):
    success: bool
    receipt_id: Optional[int] = None
    mode: ReceiptMode


# Conversational Schemas
class ChatMessage(BaseModel):
    sender: MessageSender
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[int] = None
    message: str
    language: Optional[str] = "en"


class ChatResponse(BaseModel):
    messages: List[ChatMessage]
    flow: Optional[FlowResponse] = None
    error: Optional[str] = None
    flow_steps: Optional[List[Dict[str, Any]]] = None
    transaction_intent: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

# Translation Schemas
class TranslationResponse(BaseModel):
    key: str
    value: str
    category: Optional[str] = None

# Payee Schemas
class PayeeCreate(BaseModel):
    name: str
    nickname: Optional[str] = None
    account_number: str
    routing_number: Optional[str] = None
    category: PayeeCategory
    address: Optional[str] = None
    phone: Optional[str] = None

class PayeeResponse(BaseModel):
    id: int
    name: str
    nickname: Optional[str] = None
    account_number: str
    category: PayeeCategory
    is_active: bool

class PayeeUpdate(BaseModel):
    name: Optional[str] = None
    nickname: Optional[str] = None
    is_active: Optional[bool] = None

# Cash Deposit Schemas
class CashDepositRequest(BaseModel):
    account_id: int
    bills_100: int = 0
    bills_50: int = 0
    bills_20: int = 0
    bills_10: int = 0
    bills_5: int = 0
    bills_1: int = 0
    coins_amount: float = 0.0
    envelope_used: bool = False
    receipt_mode: ReceiptMode = ReceiptMode.EMAIL

class CashDepositResponse(BaseModel):
    success: bool
    transaction_id: int
    new_balance: float
    total_deposited: float
    receipt_sent: bool = False
    message: str

# Check Deposit Schemas
class CheckDepositRequest(BaseModel):
    account_id: int
    check_number: str
    check_date: str  # Format: YYYY-MM-DD
    payer_name: str
    payer_account: Optional[str] = None
    amount: float
    check_image_front: Optional[str] = None  # Base64
    check_image_back: Optional[str] = None   # Base64
    endorsement_confirmed: bool
    receipt_mode: ReceiptMode = ReceiptMode.EMAIL

class CheckDepositResponse(BaseModel):
    success: bool
    transaction_id: int
    check_deposit_id: int
    new_balance: float
    hold_until_date: Optional[str] = None
    verification_status: CheckDepositStatus
    receipt_sent: bool = False
    message: str

# Bill Payment Schemas
class BillPaymentRequest(BaseModel):
    from_account_id: int
    payee_id: int
    amount: float
    payment_date: Optional[str] = None  # Format: YYYY-MM-DD, defaults to today
    is_recurring: bool = False
    recurrence_frequency: Optional[TransactionFrequency] = None
    end_date: Optional[str] = None
    memo: Optional[str] = None
    receipt_mode: ReceiptMode = ReceiptMode.EMAIL

class BillPaymentResponse(BaseModel):
    success: bool
    transaction_id: int
    bill_payment_id: int
    confirmation_number: str
    new_balance: float
    receipt_sent: bool = False
    message: str

# External Account Schemas
class ExternalAccountCreate(BaseModel):
    nickname: str
    bank_name: str
    account_number: str
    routing_number: str
    account_type: AccountType
    daily_transfer_limit: float = 1000.0

class ExternalAccountResponse(BaseModel):
    id: int
    nickname: str
    bank_name: str
    account_number: str  # Will be masked in response
    account_type: AccountType
    is_verified: bool
    is_active: bool

# Scheduled Transaction Schemas
class ScheduledTransactionCreate(BaseModel):
    transaction_type: str  # TRANSFER or BILL_PAYMENT
    from_account_id: int
    to_account_id: Optional[int] = None
    external_account_id: Optional[int] = None
    payee_id: Optional[int] = None
    amount: float
    scheduled_date: str  # Format: YYYY-MM-DD
    is_recurring: bool = False
    frequency: Optional[TransactionFrequency] = None
    end_date: Optional[str] = None
    memo: Optional[str] = None

class ScheduledTransactionResponse(BaseModel):
    id: int
    transaction_type: str
    amount: float
    scheduled_date: str
    is_recurring: bool
    status: str
    message: str

# Change PIN Schemas
class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str
    confirm_pin: str

class ChangePinResponse(BaseModel):
    success: bool
    message: str

# Enhanced Withdrawal Request (add receipt fields)
class WithdrawalEnhancedRequest(BaseModel):
    account_id: int
    amount: float
    preset_amount: Optional[bool] = False  # True if using preset button
    receipt_mode: ReceiptMode = ReceiptMode.EMAIL
    memo: Optional[str] = None

# New transfer request/response schemas for v2 endpoint
class TransferV2Account(BaseModel):
    Number: str
    Type: str
    Bank: Optional[str] = None

class TransferV2Request(BaseModel):
    ClientId: str
    ClientRequestNumber: str
    ClientRequestTime: str
    ClientUniqueHardwareId: str
    CardPosition: str
    SourceAccount: TransferV2Account
    DestinationAccount: TransferV2Account
    TransferAmount: float
    Currency: str

class TransferV2Response(BaseModel):
    ResponseCode: str
    TransactionAmount: float
    SourceUpdatedBalance: float
    DestinationUpdatedBalance: str
    Currency: str
    ReceiptGenerated: bool


# Enhanced Transfer Request
class TransferEnhancedRequest(BaseModel):
    from_account_id: int
    to_account_id: Optional[int] = None
    external_account_id: Optional[int] = None
    amount: float
    scheduled_date: Optional[str] = None
    is_recurring: bool = False
    frequency: Optional[TransactionFrequency] = None
    memo: Optional[str] = None
    receipt_mode: ReceiptMode = ReceiptMode.EMAIL