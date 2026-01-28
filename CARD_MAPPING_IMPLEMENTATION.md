# ATM Flow Correction & Card-to-Customer Mapping Implementation

## Overview
This update implements the correct ATM flow as per banking standards and creates proper card-to-customer mapping with support for multiple linked accounts per customer.

## Flow Changes

### Correct ATM Flow (As Per Attached Image)
1. **Welcome Screen** → Insert/tap card
2. **Card Entry** → Read track2 data (card number)
3. **Login Request** → Authenticate card with backend
4. **Language Selection** → Choose preferred language
5. **Mode Selection** → Traditional ATM or Conversational ATM
6. **PIN Entry** (Traditional ATM only) → Validate PIN
7. **Main Menu** → Access banking services

### Previous Incorrect Flow
- Combined card entry and PIN entry in one screen
- No language selection after card authentication
- Mode selection before PIN validation

## Backend Changes

### 1. New Card Model (`backend/models.py`)
```python
class Card(SQLModel, table=True):
    customer_id: int              # Links to customer
    card_number: str              # Full PAN (Track2 data)
    card_number_masked: str       # Display format (****1111)
    card_type: str                # DEBIT, CREDIT, etc.
    status: str                   # ACTIVE, BLOCKED, etc.
    expiry_date: str              # MMYY format
```

**Purpose**: Maps card numbers to customers, supporting multiple cards per customer and multiple accounts per card holder.

### 2. Updated Login Endpoint (`/auth/login`)
- Extracts card number from Track2 data
- Looks up card in database
- Validates card status
- Returns customer information and linked accounts
- Comprehensive logging at each step

### 3. Updated PIN Validation Endpoint (`/auth/pin-validation`)
- Accepts card number via `X-Card-Number` header
- Looks up customer by card number
- Validates PIN against customer's stored hash
- Returns all linked accounts for the customer
- Creates session with JWT token

### 4. Database Seed Updates (`backend/seed.py`)
- Creates card records for demo customers
- Card `4111111111111111` → John Doe (PIN: 1234)
- Card `4222222222222222` → Maria Garcia (PIN: 5678)
- Each customer has 2 linked accounts (Checking + Savings)

## Frontend Changes

### 1. New CardEntry Component
**File**: `frontend-react/src/components/CardEntry.tsx`

**Features**:
- Captures card number (Track2 data)
- Initiates login request to backend
- Comprehensive console logging
- Transitions to language selection on success

**Logs**:
```
=== CARD ENTRY FLOW START ===
[CardEntry] Card number entered: ****1111
[CardEntry] Initiating login request...
[CardEntry] Login response received: ResponseCode 00
[CardEntry] Transitioning to Language Selection
=== CARD ENTRY FLOW COMPLETE ===
```

### 2. Updated LanguageSelection Component
**Added logging**:
- Logs when language is selected
- Tracks language change process
- Logs transition to mode selection

### 3. Updated PinAuth Component
**Changes**:
- Removed card number input field
- Accepts `cardNumber` as prop
- Only displays PIN entry field
- Passes card number in API request
- Enhanced logging for PIN validation flow

**Logs**:
```
=== PIN VALIDATION FLOW START ===
[PinAuth] Card number: ****1111
[PinAuth] Phase 1: Setting preferences...
[PinAuth] Phase 2: Validating PIN...
[PinAuth] PIN validation successful!
[PinAuth] Found 2 linked accounts
[PinAuth] Transitioning to Main Menu
=== PIN VALIDATION FLOW COMPLETE ===
```

### 4. Updated WelcomeScreen Component
**Added logging**:
- Logs mode selection (Traditional/Conversational)
- Tracks transition to next screen
- Logs logout events

### 5. Updated AppContext
**New States**:
- `cardNumber: string | null` - Stores authenticated card
- `languageSelected: boolean` - Tracks language selection
- `setCardNumber()` - Sets card after authentication
- `setLanguageSelected()` - Marks language as selected

**Enhanced logging** for all state changes

### 6. Updated MainApp Orchestration
**New Flow Logic**:
```typescript
if (!cardNumber) return <CardEntry />;
if (!languageSelected) return <LanguageSelection />;
if (!mode) return <WelcomeScreen />;
if (mode === 'traditional' && !sessionId) return <PinAuth />;
return <MainApplication />;
```

**Comprehensive logging** at each decision point

### 7. Updated API Service
**Changes**:
- `validatePinAndGetAccounts()` now accepts `cardNumber` parameter
- Passes card number in `X-Card-Number` header
- Backend uses this to look up customer and validate PIN

## Database Migration

**File**: `backend/migrations/add_cards_table.sql`

Creates `cards` table with:
- Foreign key to customers table
- Unique constraint on card_number
- Indexes for performance
- Sample data for demo cards

## Card-to-Customer-to-Accounts Mapping

### Database Schema
```
Card (4111111111111111)
  ↓
Customer (John Doe, ID: 1)
  ↓
Accounts:
  - Checking: Account #1234567890 ($2,500.00)
  - Savings: Account #1234567891 ($4,200.00)
```

### Benefits
1. **Multiple Cards Per Customer**: One customer can have multiple cards
2. **Multiple Accounts Per Customer**: All accounts accessible via any card
3. **Proper Separation**: Card authentication → Customer lookup → Account access
4. **Security**: PIN validation at customer level, not card level
5. **Flexibility**: Easy to add/block cards without affecting accounts

## Logging Strategy

### Console Log Format
```
=== [FLOW NAME] START ===
[Component] Action description
[Component] Key data points
[Component] Transition information
=== [FLOW NAME] COMPLETE ===
```

### Logged Information
- Card numbers (masked for security)
- Response codes and status
- Flow transitions
- Account information
- Timestamps
- Error details

## Testing the Flow

### Step-by-Step Test
1. **Start Application**
   - Should see CardEntry screen
   - Console: `[MainApp] Rendering CardEntry - waiting for card insertion`

2. **Enter Card Number: 4111111111111111**
   - Console shows login request
   - Should transition to Language Selection
   - Console: `[CardEntry] Login successful! Setting card number in context`

3. **Select Language (English/Spanish)**
   - Console shows language change
   - Should transition to Mode Selection
   - Console: `[LanguageSelection] Transitioning to Mode Selection screen`

4. **Select Traditional ATM**
   - Console shows mode selection
   - Should transition to PIN Entry
   - Console: `[WelcomeScreen] Transitioning to PIN Entry`

5. **Enter PIN: 1234**
   - Console shows PIN validation
   - Should show account overview with 2 accounts
   - Console: `[PinAuth] Found 2 linked accounts`
   - Should transition to Main Menu

## Demo Credentials

### Customer 1: John Doe
- **Card**: 4111111111111111
- **PIN**: 1234
- **Accounts**:
  - Checking: $2,500.00
  - Savings: $4,200.00

### Customer 2: Maria Garcia
- **Card**: 4222222222222222
- **PIN**: 5678
- **Accounts**:
  - Checking: $1,800.00
  - Savings: $3,600.00

## Running the Updated Application

### Backend
```bash
cd backend
source venv/bin/activate
python seed.py  # Re-seed database with cards table
python main.py  # Start server
```

### Frontend
```bash
cd frontend-react
npm start
```

### Monitoring Logs
Open browser console (F12) to see detailed flow logging at each step.

## Security Notes

### Production Considerations
1. **Card Numbers**: Should be encrypted at rest and in transit
2. **PIN Validation**: Use proper HSM (Hardware Security Module)
3. **Track2 Data**: Should include full magnetic stripe data with encryption
4. **Session Management**: Implement proper timeout and invalidation
5. **Audit Logging**: Log all authentication attempts to database

## File Changes Summary

### Created Files
- `frontend-react/src/components/CardEntry.tsx`
- `backend/migrations/add_cards_table.sql`

### Modified Files
- `backend/models.py` - Added Card model
- `backend/main.py` - Updated login and PIN validation endpoints
- `backend/schemas.py` - Added optional fields to LoginResponse
- `backend/seed.py` - Added card creation
- `frontend-react/src/components/PinAuth.tsx` - Removed card entry, added logging
- `frontend-react/src/components/LanguageSelection.tsx` - Added logging
- `frontend-react/src/components/WelcomeScreen.tsx` - Added logging
- `frontend-react/src/components/MainApp.tsx` - Implemented correct flow logic
- `frontend-react/src/contexts/AppContext.tsx` - Added card/language states
- `frontend-react/src/services/api.ts` - Updated PIN validation to pass card number
