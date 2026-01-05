# PostgreSQL Database Schema

## Database Setup

```sql
-- Create database
CREATE DATABASE conversational_banking;

-- Create user
CREATE USER banking_user WITH PASSWORD 'banking_pass';
GRANT ALL PRIVILEGES ON DATABASE conversational_banking TO banking_user;

-- Connect to database
\c conversational_banking

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO banking_user;
```

## Tables

### 1. customers
```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    primary_email VARCHAR(255) NOT NULL,
    preferred_language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customers_email ON customers(primary_email);
```

### 2. accounts
```sql
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('CHECKING', 'SAVINGS')),
    currency VARCHAR(3) DEFAULT 'USD',
    balance DECIMAL(15, 2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_accounts_customer ON accounts(customer_id);
CREATE INDEX idx_accounts_type ON accounts(type);
```

### 3. sessions
```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    card_number VARCHAR(20) NOT NULL,
    pin_attempts INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'LOCKED')),
    channel VARCHAR(20) DEFAULT 'web',
    jwt_token TEXT,
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_sessions_customer ON sessions(customer_id);
CREATE INDEX idx_sessions_card ON sessions(card_number);
CREATE INDEX idx_sessions_status ON sessions(status);
```

### 4. transaction_intents
```sql
CREATE TABLE transaction_intents (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    operation VARCHAR(30) NOT NULL CHECK (operation IN ('WITHDRAW', 'DEPOSIT', 'TRANSFER', 'PAYMENT', 'BALANCE_INQUIRY')),
    from_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    to_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    amount DECIMAL(15, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    receipt_preference VARCHAR(20) DEFAULT 'NONE' CHECK (receipt_preference IN ('PRINT', 'EMAIL', 'NONE')),
    status VARCHAR(30) DEFAULT 'PENDING_DETAILS' CHECK (status IN ('PENDING_DETAILS', 'READY_TO_EXECUTE', 'COMPLETED', 'CANCELLED')),
    missing_fields TEXT,
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intents_session ON transaction_intents(session_id);
CREATE INDEX idx_intents_status ON transaction_intents(status);
```

### 5. transactions
```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    intent_id INTEGER REFERENCES transaction_intents(id) ON DELETE SET NULL,
    operation VARCHAR(30) NOT NULL CHECK (operation IN ('WITHDRAW', 'DEPOSIT', 'TRANSFER', 'PAYMENT', 'BALANCE_INQUIRY')),
    from_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    to_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT
);

CREATE INDEX idx_transactions_intent ON transactions(intent_id);
CREATE INDEX idx_transactions_from_account ON transactions(from_account_id);
CREATE INDEX idx_transactions_to_account ON transactions(to_account_id);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
```

### 6. receipts
```sql
CREATE TABLE receipts (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('PRINT', 'EMAIL', 'NONE')),
    email VARCHAR(255),
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_receipts_transaction ON receipts(transaction_id);
```

### 7. screen_flows
```sql
CREATE TABLE screen_flows (
    id SERIAL PRIMARY KEY,
    intent_id INTEGER NOT NULL REFERENCES transaction_intents(id) ON DELETE CASCADE,
    steps TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_flows_intent ON screen_flows(intent_id);
```

### 8. conversation_messages
```sql
CREATE TABLE conversation_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sender VARCHAR(20) NOT NULL CHECK (sender IN ('USER', 'ASSISTANT', 'SYSTEM')),
    content TEXT NOT NULL,
    channel VARCHAR(20) DEFAULT 'web',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_metadata TEXT
);

CREATE INDEX idx_messages_session ON conversation_messages(session_id);
CREATE INDEX idx_messages_created ON conversation_messages(created_at);
```

## Sample Data

```sql
-- Insert sample customers
INSERT INTO customers (name, primary_email, preferred_language) VALUES
('John Doe', 'john.doe@example.com', 'en'),
('Maria Garcia', 'maria.garcia@example.com', 'es');

-- Insert sample accounts (adjust customer_id based on actual IDs)
INSERT INTO accounts (customer_id, type, currency, balance, status) VALUES
(1, 'CHECKING', 'USD', 2500.00, 'ACTIVE'),
(1, 'SAVINGS', 'USD', 4200.00, 'ACTIVE'),
(2, 'CHECKING', 'USD', 1800.00, 'ACTIVE'),
(2, 'SAVINGS', 'USD', 3600.00, 'ACTIVE');
```

## Demo Credentials

- **Customer 1:** Card: `4111111111111111`, PIN: `1234`
- **Customer 2:** Card: `4222222222222222`, PIN: `5678`
