# API Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONVERSATIONAL BANKING ATM API FLOW                      │
└─────────────────────────────────────────────────────────────────────────────┘

PHASE 1: LOGIN
┌──────────────┐                                              ┌──────────────┐
│    Client    │  POST /auth/login                            │    Server    │
│   (ATM/Web)  │  ─────────────────────────────────────────>  │   (Backend)  │
│              │  - ClientId                                   │              │
│              │  - ConsumerIdentificationData (Track2, EMV)   │              │
│              │                                               │              │
│              │  <─────────────────────────────────────────   │              │
│              │  - ResponseCode: "00"                         │              │
│              │  - EnabledTransactions                        │              │
│              │  - CardProductProperties                      │              │
└──────────────┘                                              └──────────────┘

PHASE 2: PREFERENCES
┌──────────────┐                                              ┌──────────────┐
│    Client    │  POST /preferences                           │    Server    │
│              │  ─────────────────────────────────────────>  │              │
│              │  - Language, EmailID                          │              │
│              │  - ReceiptPreference                          │              │
│              │  - FastCashPreference                         │              │
│              │                                               │              │
│              │  <─────────────────────────────────────────   │              │
│              │  - CustomerId                                 │              │
│              │  - SessionLanguageCode                        │              │
│              │  - FastCashSourceAccountNumber                │              │
└──────────────┘                                              └──────────────┘

PHASE 3: PIN VALIDATION + ACCOUNT OVERVIEW
┌──────────────┐                                              ┌──────────────┐
│    Client    │  POST /auth/pin-validation                   │    Server    │
│              │  ─────────────────────────────────────────>  │              │
│              │  - EncryptedPinData                           │              │
│              │  - EmvAuthorizeRequestData                    │              │
│              │                                               │              │
│              │  <─────────────────────────────────────────   │              │
│              │  - ActionCode: "Approved"                     │              │
│              │  - Accounts[] (with balances)                 │              │
│              │  - SupportedTransactions                      │              │
└──────────────┘                                              └──────────────┘

PHASE 4: ACCOUNT OVERVIEW FINALIZATION
┌──────────────┐                                              ┌──────────────┐
│    Client    │  POST /account-overview/finalize             │    Server    │
│              │  ─────────────────────────────────────────>  │              │
│              │  - ClientTransactionResult: "Confirmed"       │              │
│              │  - AccountingState: "Final"                   │              │
│              │  - EmvFinalizeRequestData                     │              │
│              │                                               │              │
│              │  <─────────────────────────────────────────   │              │
│              │  - ResponseCode: "00"                         │              │
│              │  - EnabledTransactions                        │              │
└──────────────┘                                              └──────────────┘

PHASE 5: WITHDRAWAL AUTHORIZATION
┌──────────────┐                                              ┌──────────────┐
│    Client    │  POST /transactions/withdrawal/authorize     │    Server    │
│              │  ─────────────────────────────────────────>  │              │
│              │  - SourceAccount                              │              │
│              │  - RequestedAmount                            │              │
│              │  - EncryptedPinData (re-validation)           │              │
│              │                                               │              │
│              │  <─────────────────────────────────────────   │              │
│              │  - ActionCode: "Approved"                     │              │
│              │  - TransactionAmount                          │              │
│              │  - AccountInformation (updated balance)       │              │
│              │  - WithdrawalDailyLimits                      │              │
└──────────────┘                                              └──────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                             RESPONSE CODES                                   │
├──────────────┬──────────────────────────────────────────────────────────────┤
│     Code     │                     Description                               │
├──────────────┼──────────────────────────────────────────────────────────────┤
│     00       │  Success / Approved                                           │
│     51       │  Insufficient Funds                                           │
│     55       │  Incorrect PIN                                                │
│     75       │  PIN Tries Exceeded                                           │
│     91       │  Issuer Unavailable                                           │
└──────────────┴──────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FLOW SUMMARY                                   │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT (Phase 1)                    OUTPUT (Phase 5)
─────────────────                  ──────────────────
• Card Data (Track2)        ──┐    • Transaction Approved
• EMV Tags                    │    • Account Debited
• Hardware ID                 │    • Updated Balance
                              │    • Daily Limits Info
                           ┌──┴──┐ • Receipt Data
                           │     │
                           │ API │
                           │ Flow│
                           │     │
                           └──┬──┘
                              │
Intermediate Steps:           │
• User Preferences            │
• Language Selection          │
• Email for Receipt           │
• PIN Validation              │
• Account Overview            │
• Transaction Confirmation    │
                              └──> Complete Transaction


┌─────────────────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                                       │
└─────────────────────────────────────────────────────────────────────────────┘

Layer 1: Card Authentication (Login)
  └─> Track2 Data + EMV Verification

Layer 2: PIN Validation
  └─> Encrypted PIN Block + EMV Cryptogram

Layer 3: Transaction Authorization
  └─> Re-PIN Validation + Balance Check + Limit Validation

Layer 4: EMV Finalization
  └─> EMV Tag Updates + Transaction Log
