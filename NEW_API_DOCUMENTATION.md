# New API Endpoints Documentation

This document describes the updated API request and response flow based on the SampleRequest-Response specification.

## Overview

The API has been updated to support a standard ATM transaction flow with 5 main phases:

1. **Login Phase** - Card authentication and capability discovery
2. **Preferences Phase** - User preference configuration
3. **PIN Validation + Account Overview** - PIN verification and account information retrieval
4. **Account Overview Finalization** - Confirmation of account overview phase
5. **Withdrawal Authorization** - Transaction processing and execution

---

## 1. Login Phase

### Endpoint: `POST /auth/login`

Authenticates the card and returns enabled transactions and card capabilities.

#### Request Body
```json
{
  "ClientId": "ATM123",
  "ClientRequestNumber": "REQ001",
  "ClientRequestTime": "2026-01-07T07:42:00Z",
  "ClientUniqueHardwareId": "HW987654",
  "ConsumerIdentificationData": {
    "Track2": "1234567890123456=26012010000000000000",
    "EMVTags": ["9F02", "5F2A"],
    "ManualDataType": "EMV"
  }
}
```

#### Response Body
```json
{
  "ResponseCode": "00",
  "EnabledTransactions": ["Withdrawal", "BalanceInquiry","CashDeposit","CheckDeposit","Transfer","Payments","PinChange"],
  "ConsumerGroup": "Retail",
  "ExtendedTransactionResponseCode": "00",
  "CardDataElementEntitlements": ["PIN", "FastCash"],
  "CardProductProperties": {
    "MinPinLength": 4,
    "MaxPinLength": 6,
    "FastSupported": true,
    "FastCashAmount": 100
  },
  "TransactionsSupported": ["Withdrawal", "BalanceInquiry","CashDeposit","CheckDeposit","Transfer","Payments","PinChange"]
}
```

#### Fields Description

**Request:**
- `ClientId`: ATM terminal identifier
- `ClientRequestNumber`: Unique request sequence number
- `ClientRequestTime`: ISO 8601 timestamp
- `ClientUniqueHardwareId`: Hardware identifier for the ATM
- `ConsumerIdentificationData`: Card data including Track2 and EMV tags

**Response:**
- `ResponseCode`: "00" for success
- `EnabledTransactions`: List of available transaction types
- `ConsumerGroup`: Customer segment classification
- `CardProductProperties`: Card-specific capabilities and limits

---

## 2. Preferences Phase

### Endpoint: `POST /preferences`

Sets user preferences including language, email, receipt delivery method, and fast cash options.

#### Request Body
```json
{
  "ClientId": "ATM123",
  "ClientRequestNumber": "REQ002",
  "ClientRequestTime": "2026-01-07T07:43:00Z",
  "ClientUniqueHardwareId": "HW987654",
  "CardPosition": "Inserted",
  "Preferences": {
    "Language": "EN",
    "EmailID": "user@example.com",
    "ReceiptPreference": "Email",
    "FastCashPreference": true
  }
}
```

#### Response Body
```json
{
  "AuthorizerResponseCode": "00",
  "AcquirerResponseCode": "00",
  "ActionCode": "Approved",
  "MessageSequenceNumber": "MSG001",
  "CustomerId": "CUST123456",
  "SessionLanguageCode": "EN",
  "EmailAddress": "user@example.com",
  "ReceiptPreferenceCode": "E",
  "FastCashTransactionAmount": 100,
  "FastCashSourceAccountNumber": "9876543210",
  "FastCashSourceProductTypeCode": "SAV"
}
```

#### Fields Description

**Request:**
- `CardPosition`: Physical card status (Inserted/Removed)
- `Preferences.Language`: ISO language code
- `Preferences.EmailID`: Customer email for receipts
- `Preferences.ReceiptPreference`: Print/Email/None
- `Preferences.FastCashPreference`: Enable quick cash withdrawal

**Response:**
- `ReceiptPreferenceCode`: "E" for Email, "P" for Print
- `FastCashTransactionAmount`: Pre-configured fast cash amount
- `FastCashSourceAccountNumber`: Default account for fast cash

---

## 3. PIN Validation + Account Overview

### Endpoint: `POST /auth/pin-validation`

Validates the customer PIN and returns account information.

#### Request Body
```json
{
  "ClientId": "ATM123",
  "ClientRequestNumber": "REQ003",
  "EncryptedPinData": "ABCD1234XYZ",
  "EmvAuthorizeRequestData": {
    "Tag57": "value",
    "Tag5FA": "value"
  },
  "Breadcrumb": "Step3"
}
```

#### Response Body
```json
{
  "AuthorizerResponseCode": "00",
  "AcquirerResponseCode": "00",
  "ActionCode": "Approved",
  "MessageSequenceNumber": "MSG002",
  "IssuerResponseCode": "00",
  "PrimaryAccountNumber": "9876543210",
  "CptCardClassCode": "CLASS1",
  "TransactionMode": "Online",
  "Breadcrumb": "Step3",
  "ResponseCode": "00",
  "IntendedWkstState": "Active",
  "HostResponseCode": "00",
  "Accounts": [
    {
      "AccountNumber": "9876543210",
      "Balance": 5000,
      "Currency": "USD"
    }
  ],
  "SupportedTransactions": ["Withdrawal", "BalanceInquiry"]
}
```

#### Fields Description

**Request:**
- `EncryptedPinData`: Encrypted PIN block
- `EmvAuthorizeRequestData`: EMV chip data tags
- `Breadcrumb`: Navigation tracking identifier

**Response:**
- `Accounts`: Array of customer accounts with balances
- `PrimaryAccountNumber`: Primary linked account
- `TransactionMode`: Online/Offline processing mode

---

## 4. Account Overview Finalization

### Endpoint: `POST /account-overview/finalize`

Finalizes the account overview phase and prepares for transaction execution.

#### Request Body
```json
{
  "ClientId": "ATM123",
  "ClientRequestNumber": "REQ004",
  "ClientRequestTime": "2026-01-07T07:44:00Z",
  "ClientUniqueHardwareId": "HW987654",
  "CardPosition": "Inserted",
  "ClientTransactionResult": "Confirmed",
  "AccountingState": "Final",
  "CardUpdateState": "NoUpdate",
  "EmvFinalizeRequestData": {
    "Tags": ["9F02", "5F2A"]
  }
}
```

#### Response Body
```json
{
  "ExtendedTransactionResponseCode": "00",
  "ResponseCode": "00",
  "IntendedWkstState": "Active",
  "EnabledTransactions": ["Withdrawal", "BalanceInquiry"]
}
```

#### Fields Description

**Request:**
- `ClientTransactionResult`: Confirmed/Cancelled
- `AccountingState`: Final/Pending/Reversed
- `CardUpdateState`: Update status for EMV chip
- `EmvFinalizeRequestData`: EMV finalization tags

**Response:**
- `IntendedWkstState`: Next state for the ATM workstation
- `EnabledTransactions`: Available transaction types for next step

---

## 5. Withdrawal Authorization

### Endpoint: `POST /transactions/withdrawal/authorize`

Authorizes and processes a cash withdrawal transaction.

#### Request Body
```json
{
  "ClientId": "ATM123",
  "ClientRequestNumber": "REQ005",
  "ClientRequestTime": "2026-01-07T07:45:00Z",
  "ClientUniqueHardwareId": "HW987654",
  "CardPosition": "Inserted",
  "HostTransactionNumber": "TXN123456",
  "EncryptedPinData": "ABCD1234XYZ",
  "EmvAuthorizeRequestData": {
    "Tag57": "value",
    "Tag5FA": "value"
  },
  "CardTechnology": "EMV",
  "SourceAccount": {
    "Number": "9876543210",
    "Type": "SAV",
    "Subtype": "Regular"
  },
  "RequestedAmount": 100,
  "Currency": "USD"
}
```

#### Response Body
```json
{
  "AuthorizerResponseCode": "00",
  "AcquirerResponseCode": "00",
  "ActionCode": "Approved",
  "MessageSequenceNumber": "MSG003",
  "CptCardClassCode": "CLASS1",
  "TransactionMode": "Online",
  "TransactionAmount": 100,
  "Currency": "USD",
  "FractionDigits": 2,
  "DebitedAccount": {
    "AccountNumber": "9876543210",
    "AccountType": "SAV",
    "Subtype": "Regular"
  },
  "WithdrawalDailyLimits": {
    "Amount": 500,
    "CurrencyCode": "USD",
    "FractionDigits": 2
  },
  "ResponseCode": "00",
  "EnabledTransactions": ["Withdrawal", "BalanceInquiry"],
  "EmvAuthorizeResponseData": {
    "Tag57": "value",
    "Tag5FA": "value"
  },
  "AccountInformation": {
    "Balance": 4900,
    "CurrencyCode": "USD",
    "FractionDigits": 2
  },
  "PossibleLimits": ["DailyLimit", "PerTransactionLimit"]
}
```

#### Fields Description

**Request:**
- `HostTransactionNumber`: Unique transaction identifier
- `CardTechnology`: EMV/Magnetic/Contactless
- `SourceAccount`: Account to debit from
- `RequestedAmount`: Amount to withdraw

**Response:**
- `DebitedAccount`: Account that was debited
- `WithdrawalDailyLimits`: Remaining daily limits
- `AccountInformation.Balance`: Updated balance after withdrawal
- `PossibleLimits`: Active limit types

---

## Response Codes

| Code | Description |
|------|-------------|
| 00   | Success/Approved |
| 51   | Insufficient funds |
| 55   | Incorrect PIN |
| 75   | PIN tries exceeded |
| 91   | Issuer unavailable |

---

## Testing

To test the new endpoints, run the provided test script:

```bash
cd backend
python test_new_endpoints.py
```

Make sure the backend server is running:

```bash
cd backend
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
uvicorn main:app --reload
```

---

## Migration Notes

### Backward Compatibility

The existing `/auth/pin` endpoint has been preserved for backward compatibility. The new endpoints follow the standardized ATM protocol format.

### Integration Steps

1. Update client applications to use the new endpoint structure
2. Map Track2 data to card numbers in the login phase
3. Implement proper PIN encryption/decryption
4. Handle EMV tag data appropriately for chip cards
5. Implement session management across the 5 phases

---

## Security Considerations

1. **PIN Encryption**: All PIN data must be encrypted using industry-standard methods (e.g., DUKPT, 3DES)
2. **EMV Compliance**: Ensure proper handling of EMV tags according to EMVCo specifications
3. **Session Management**: Implement proper session timeouts and token expiration
4. **Transaction Logging**: Log all transactions for audit and reconciliation
5. **Rate Limiting**: Implement rate limiting on all endpoints to prevent abuse

---

## Next Steps

1. Integrate with actual payment processing system
2. Implement proper EMV tag parsing and validation
3. Add transaction reversal endpoints
4. Implement receipt generation and delivery
5. Add balance inquiry and mini-statement endpoints
6. Implement proper error handling and retry logic
