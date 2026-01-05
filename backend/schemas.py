"""Pydantic schemas for API request/response models."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from models import (
    AccountType, OperationType, IntentStatus,
    TransactionStatus, ReceiptMode, MessageSender
)


# Auth Schemas
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
