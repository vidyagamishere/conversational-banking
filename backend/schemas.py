"""Pydantic schemas for API request/response models."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from models import (
    AccountType, OperationType, IntentStatus,
    TransactionStatus, ReceiptMode, MessageSender
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
    EnabledTransactions: List[str]
    ConsumerGroup: str
    ExtendedTransactionResponseCode: str
    CardDataElementEntitlements: List[str]
    CardProductProperties: CardProductProperties
    TransactionsSupported: List[str]


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
    AccountNumber: str
    Balance: float
    Currency: str


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
