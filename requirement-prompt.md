
Conversational ATM Banking Demo – System Specification
This document describes the requirements for a conversational ATM banking demo that can power web and future mobile conversational flows.

Frontend: React + TypeScript SPA (web first, material UI based, future‑friendly for mobile).

Backend: FastAPI + Python, Postgres via SQLAlchemy/SQLModel.
​

LLM: Orchestrator using an Ollama‑hosted model that calls backend routes as tools.
​

All data flows via JSON.

1. Frontend Requirements (React SPA)
Implement a React + TypeScript web app that talks only to HTTP JSON APIs.

1.1 Screens
Welcome screen

Language selection (e.g., English, Spanish) with simple i18n structure.

Mode selection:

“Conversational ATM”

“Traditional ATM”

PIN / Authentication

Card number input (or simple card selector).

Masked PIN field.

Error on invalid PIN, lock after N attempts, driven by backend response.

Conversational ATM Screen

Chat transcript area.

Text input box.

“Trending transaction” buttons, e.g.:

“Withdraw 100 dollars from my checking account.”

“Transfer 50 dollars from checking to savings.”

A panel or button to show remote ATM screen flow.

An Interrupt button when a remote flow is running.

Integration:

Calls POST /channels/web/chat with JSON:

{ sessionId, message }.

Renders:

Assistant messages from the response.

Any extra payloads (e.g., screen flow JSON, hints).

Traditional ATM Screen

Menu‑driven UI:

Balance inquiry.

Account details.

Withdraw.

Deposit.

Transfer.

Payment.

Receipts.

Each operation:

Structured forms (account pickers, numeric amount fields).

Calls REST endpoints such as /accounts/summary, /transactions/withdraw, etc.

Remote Screen Flow Viewer

Reads a JSON flow object from backend:

Example: { flowId, intentId, steps: [{ id, label, screenType? }, ...] }.

Animates through steps after transaction execution.

Supports interrupt:

On “Interrupt”, call POST /flows/{flowId}/interrupt.

1.2 State Management
Store in React context or equivalent:

sessionId.

Selected language.

Current mode (conversational/traditional).

Conversation history (for UI only).

Never fake balances or transactions on the frontend; always use backend responses.

1.3 Future Channels
Keep conversational logic in a small “conversation service” that wraps:

POST /channels/web/chat.

Mobile apps or other clients can later reuse the same backend contract with minimal UI changes.

2. Backend: FastAPI Domain API (No LLM)
Implement FastAPI routes that encapsulate all domain logic. Use Pydantic for request/response models and SQLAlchemy/SQLModel for Postgres.
​

2.1 Auth Routes
text
POST /auth/pin
Request JSON:

json
{
  "cardNumber": "string",
  "pin": "string"
}
Response JSON:

json
{
  "success": true,
  "sessionId": "string or null",
  "customerId": "string or null",
  "remainingAttempts": 2,
  "error": "string or null"
}
2.2 Account Routes
text
GET /accounts/summary
Query or body:

json
{ "sessionId": "string" }
Response:

json
{
  "accounts": [
    {
      "accountId": "string",
      "type": "CHECKING",
      "currency": "USD",
      "balance": 1200.50
    }
  ]
}
text
GET /accounts/{accountId}/details
Query or body:

json
{ "sessionId": "string" }
Response:

json
{
  "accountId": "string",
  "type": "CHECKING",
  "currency": "USD",
  "balance": 1200.50,
  "transactions": [
    {
      "transactionId": "string",
      "operation": "WITHDRAW",
      "amount": 100.0,
      "currency": "USD",
      "timestamp": "2026-01-05T12:00:00Z",
      "description": "ATM withdrawal"
    }
  ]
}
2.3 Conversational Intent Routes
text
POST /conversation/intents
Request:

json
{
  "sessionId": "string",
  "naturalLanguageRequest": "Withdraw 100 dollars from my checking account"
}
Response:

json
{
  "intentId": "string",
  "operation": "WITHDRAW",
  "status": "PENDING_DETAILS",
  "fromAccountId": "string or null",
  "toAccountId": "string or null",
  "amount": 100.0,
  "currency": "USD",
  "receiptPreference": "EMAIL",
  "missingFields": ["pinConfirmed"],
  "clarificationQuestions": [
    "Please confirm your PIN."
  ]
}
text
POST /conversation/intents/{intentId}/update
Request:

json
{
  "sessionId": "string",
  "answers": {
    "pin": "1234",
    "fromAccountId": "acc-checking-001",
    "toAccountId": null,
    "amount": 100.0,
    "receiptPreference": "EMAIL",
    "confirm": true
  }
}
Response:

json
{
  "intentId": "intent-001",
  "status": "READY_TO_EXECUTE",
  "missingFields": [],
  "summary": {
    "operation": "WITHDRAW",
    "fromAccountId": "acc-checking-001",
    "toAccountId": null,
    "amount": 100.0,
    "currency": "USD",
    "receiptPreference": "EMAIL"
  }
}
2.4 Transaction Routes
text
POST /transactions/execute
Request:

json
{
  "sessionId": "string",
  "intentId": "string"
}
Response:

json
{
  "success": true,
  "transaction": {
    "transactionId": "txn-12345",
    "operation": "WITHDRAW",
    "fromAccountId": "acc-checking-001",
    "toAccountId": null,
    "amount": 100.0,
    "currency": "USD",
    "status": "COMPLETED",
    "timestamp": "2026-01-05T12:00:00Z"
  },
  "updatedBalances": {
    "acc-checking-001": 1100.50
  },
  "error": null
}
Traditional structured operations (reusing the same services):

text
POST /transactions/withdraw
POST /transactions/deposit
POST /transactions/transfer
POST /transactions/payment
Each accepts a body like:

json
{
  "sessionId": "string",
  "fromAccountId": "string",
  "toAccountId": "string or null",
  "amount": 200.0,
  "currency": "USD",
  "receiptPreference": "NONE"
}
and returns the same transaction + updatedBalances shape.

2.5 Remote Screen Flow Routes
text
GET /flows/{intentId}
Query or body:

json
{ "sessionId": "string" }
Response:

json
{
  "flowId": "flow-001",
  "intentId": "intent-001",
  "steps": [
    { "id": "selectOperation", "label": "Select operation: WITHDRAW", "screenType": "SELECT" },
    { "id": "selectAccount", "label": "Select account: acc-checking-001", "screenType": "SELECT" },
    { "id": "confirmAmount", "label": "Confirm amount: 100.0 USD", "screenType": "CONFIRM" },
    { "id": "processing", "label": "Processing transaction...", "screenType": "PROCESSING" },
    { "id": "success", "label": "Transaction completed.", "screenType": "SUCCESS" }
  ]
}
text
POST /flows/{flowId}/interrupt
Request:

json
{ "sessionId": "string" }
Response:

json
{
  "flowId": "flow-001",
  "status": "INTERRUPTED",
  "intent": {
    "intentId": "intent-001",
    "status": "PENDING_DETAILS",
    "summary": { /* same structure as in intents */ }
  }
}
2.6 Receipt Routes
text
POST /receipts
Request:

json
{
  "sessionId": "string",
  "transactionId": "txn-12345",
  "mode": "PRINT",
  "email": "customer@example.com"
}
Response:

json
{
  "success": true,
  "receiptId": "rcpt-98765",
  "mode": "PRINT"
}
3. LLM Orchestrator (Ollama Agent)
Create a Python orchestration layer that uses an Ollama‑hosted open‑source model to interpret user messages and call domain APIs as tools.
​

3.1 Channel Gateway Route
text
POST /channels/web/chat
Request:

json
{
  "sessionId": "string or null",
  "message": "string",
  "language": "string or null"
}
Response:

json
{
  "messages": [
    { "sender": "USER", "content": "I want to withdraw 100 dollars from checking." },
    { "sender": "ASSISTANT", "content": "Sure, from which account? Checking or savings?" }
  ],
  "flow": {
    "flowId": "flow-001",
    "intentId": "intent-001",
    "steps": [ /* same structure as /flows/{intentId} */ ]
  },
  "error": null
}
3.2 Orchestrator Behavior
For each POST /channels/web/chat call:

Load conversation history for sessionId (or create new).

Call Ollama with:

System prompt defining ATM rules (PIN required, no hallucinated balances, always summarize before execute, etc.).

Conversation history.

Tool definitions mapping to:

/auth/pin

/accounts/summary

/accounts/{accountId}/details

/conversation/intents

/conversation/intents/{intentId}/update

/transactions/execute

/flows/{intentId}

/flows/{flowId}/interrupt

/receipts

Execute tool calls by invoking internal service functions (or the FastAPI app directly).

Feed tool results back to the model until it produces a final natural‑language response.

Return:

Assistant messages.

Optional flow object for remote screen visualization.

Keep orchestrator logic in a separate module so future channel routes (e.g., /channels/mobile/chat) can reuse it.

4. Database Requirements (Postgres)
Use Postgres as the single source of truth for state, compatible with multiple channels.
​

4.1 Core Tables
customers

id

name

primary_email

preferred_language

created_at

updated_at

accounts

id

customer_id (FK → customers)

type (CHECKING / SAVINGS)

currency

balance

status

created_at

updated_at

sessions

id

customer_id (FK → customers)

card_number

pin_attempts

status

channel (e.g., web, mobile)

created_at

expires_at

transaction_intents

id

session_id (FK → sessions)

operation (enum)

from_account_id (FK → accounts, nullable)

to_account_id (FK → accounts, nullable)

amount

currency

receipt_preference

status

missing_fields (JSONB)

context (JSONB)

created_at

updated_at

transactions

id

intent_id (FK → transaction_intents)

operation

from_account_id

to_account_id

amount

currency

status

timestamp

metadata (JSONB)

receipts

id

transaction_id (FK → transactions)

mode (PRINT / EMAIL / NONE)

email

content (JSONB or text)

created_at

(Optional) screen_flows

id

intent_id or transaction_id

steps (JSONB)

status

created_at

updated_at

(Optional) conversation_messages

id

session_id (FK → sessions)

sender (USER / ASSISTANT / SYSTEM)

content

channel

created_at

metadata (JSONB)

4.2 Seeding
Seed Postgres with:

1–2 mock customers.

Checking and savings accounts with realistic balances.

A few historical transactions for demo.

Use this spec as a guide for GitHub Copilot or other coding assistants to scaffold:

FastAPI routes and Pydantic models.

SQLAlchemy/SQLModel models and migrations.

React SPA wired to /channels/web/chat and REST routes.

Ollama‑based LLM orchestrator that executes the ATM flows end‑to‑end.