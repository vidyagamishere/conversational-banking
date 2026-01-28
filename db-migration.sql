-- ============================================================================
-- Database Migration Script for Conversational Banking ATM
-- Version: 2.0
-- Date: January 24, 2026
-- Description: Adds new features for Check Deposit, Bill Payment, PIN Change,
--              External Accounts, Scheduled Transactions, and enhancements
-- ============================================================================

-- ============================================================================
-- PART 1: ALTER EXISTING TABLES
-- ============================================================================

-- 1.1 Add new columns to customers table
ALTER TABLE customers 
ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(255),
ADD COLUMN IF NOT EXISTS pin_change_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_pin_change TIMESTAMP,
ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10) DEFAULT 'en';

-- Create index on preferred_language for filtering
CREATE INDEX IF NOT EXISTS idx_customers_language ON customers(preferred_language);

-- 1.2 Add new columns to accounts table
ALTER TABLE accounts
ADD COLUMN IF NOT EXISTS account_number VARCHAR(20),
ADD COLUMN IF NOT EXISTS account_number_masked VARCHAR(20),
ADD COLUMN IF NOT EXISTS daily_withdrawal_limit DECIMAL(15, 2) DEFAULT 500.00,
ADD COLUMN IF NOT EXISTS daily_deposit_limit DECIMAL(15, 2) DEFAULT 10000.00,
ADD COLUMN IF NOT EXISTS daily_transfer_limit DECIMAL(15, 2) DEFAULT 5000.00;

-- Update existing accounts with account numbers if not present
UPDATE accounts 
SET account_number = CONCAT('ACC', LPAD(id::TEXT, 10, '0')),
    account_number_masked = CONCAT('****', RIGHT(CONCAT('ACC', LPAD(id::TEXT, 10, '0')), 4))
WHERE account_number IS NULL;

-- Create unique index on account_number
CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_number ON accounts(account_number);

-- 1.3 Add new columns to transactions table
ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS memo TEXT,
ADD COLUMN IF NOT EXISTS receipt_mode VARCHAR(20) DEFAULT 'NONE',
ADD COLUMN IF NOT EXISTS receipt_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS is_scheduled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS scheduled_date DATE;

-- Add constraint for receipt_mode
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_receipt_mode_check;
ALTER TABLE transactions ADD CONSTRAINT transactions_receipt_mode_check 
CHECK (receipt_mode IN ('PRINT', 'EMAIL', 'NONE'));

-- 1.4 Update transaction_intents to support new operation types
ALTER TABLE transaction_intents DROP CONSTRAINT IF EXISTS transaction_intents_operation_check;
ALTER TABLE transaction_intents ADD CONSTRAINT transaction_intents_operation_check 
CHECK (operation IN ('WITHDRAW', 'DEPOSIT', 'CASH_DEPOSIT', 'CHECK_DEPOSIT', 'TRANSFER', 'PAYMENT', 'BILL_PAYMENT', 'BALANCE_INQUIRY', 'PIN_CHANGE'));

-- ============================================================================
-- PART 2: CREATE NEW TABLES
-- ============================================================================

-- 2.1 Create pin_history table
CREATE TABLE IF NOT EXISTS pin_history (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    pin_hash VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(50) DEFAULT 'SELF',
    ip_address VARCHAR(50),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_pin_history_customer ON pin_history(customer_id);
CREATE INDEX IF NOT EXISTS idx_pin_history_changed_at ON pin_history(changed_at);

COMMENT ON TABLE pin_history IS 'Tracks PIN change history for security and audit purposes';

-- 2.2 Create payees table
CREATE TABLE IF NOT EXISTS payees (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    nickname VARCHAR(100),
    account_number VARCHAR(50) NOT NULL,
    routing_number VARCHAR(20),
    category VARCHAR(30) NOT NULL CHECK (category IN ('UTILITY', 'CREDIT_CARD', 'LOAN', 'INSURANCE', 'RENT', 'MORTGAGE', 'PHONE', 'INTERNET', 'OTHER')),
    address TEXT,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_payees_customer ON payees(customer_id);
CREATE INDEX IF NOT EXISTS idx_payees_category ON payees(category);
CREATE INDEX IF NOT EXISTS idx_payees_active ON payees(is_active);

COMMENT ON TABLE payees IS 'Stores bill payment payee information for customers';

-- 2.3 Create bill_payments table
CREATE TABLE IF NOT EXISTS bill_payments (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    payee_id INTEGER NOT NULL REFERENCES payees(id) ON DELETE RESTRICT,
    payment_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_frequency VARCHAR(20) CHECK (recurrence_frequency IN ('WEEKLY', 'BIWEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')),
    next_payment_date DATE,
    end_date DATE,
    memo TEXT,
    confirmation_number VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bill_payments_transaction ON bill_payments(transaction_id);
CREATE INDEX IF NOT EXISTS idx_bill_payments_payee ON bill_payments(payee_id);
CREATE INDEX IF NOT EXISTS idx_bill_payments_date ON bill_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_bill_payments_recurring ON bill_payments(is_recurring);

COMMENT ON TABLE bill_payments IS 'Stores bill payment transaction details';

-- 2.4 Create check_deposits table
CREATE TABLE IF NOT EXISTS check_deposits (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    check_number VARCHAR(50) NOT NULL,
    check_date DATE NOT NULL,
    payer_name VARCHAR(255) NOT NULL,
    payer_account VARCHAR(50),
    check_image_front TEXT,
    check_image_back TEXT,
    endorsement_confirmed BOOLEAN DEFAULT FALSE,
    hold_until_date DATE,
    hold_reason VARCHAR(100),
    verification_status VARCHAR(30) DEFAULT 'PENDING' CHECK (verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'ON_HOLD')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_check_deposits_transaction ON check_deposits(transaction_id);
CREATE INDEX IF NOT EXISTS idx_check_deposits_check_number ON check_deposits(check_number);
CREATE INDEX IF NOT EXISTS idx_check_deposits_status ON check_deposits(verification_status);
CREATE INDEX IF NOT EXISTS idx_check_deposits_date ON check_deposits(check_date);

COMMENT ON TABLE check_deposits IS 'Stores check deposit details including images and verification status';

-- 2.5 Create cash_deposits table
CREATE TABLE IF NOT EXISTS cash_deposits (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    bills_100 INTEGER DEFAULT 0,
    bills_50 INTEGER DEFAULT 0,
    bills_20 INTEGER DEFAULT 0,
    bills_10 INTEGER DEFAULT 0,
    bills_5 INTEGER DEFAULT 0,
    bills_1 INTEGER DEFAULT 0,
    total_bills DECIMAL(15, 2),
    coins_amount DECIMAL(10, 2) DEFAULT 0.00,
    total_amount DECIMAL(15, 2) NOT NULL,
    envelope_used BOOLEAN DEFAULT FALSE,
    verification_status VARCHAR(30) DEFAULT 'VERIFIED' CHECK (verification_status IN ('PENDING', 'VERIFIED', 'DISCREPANCY')),
    verified_amount DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cash_deposits_transaction ON cash_deposits(transaction_id);
CREATE INDEX IF NOT EXISTS idx_cash_deposits_status ON cash_deposits(verification_status);

COMMENT ON TABLE cash_deposits IS 'Stores denomination breakdown for cash deposits';

-- 2.6 Create external_accounts table
CREATE TABLE IF NOT EXISTS external_accounts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    nickname VARCHAR(100) NOT NULL,
    bank_name VARCHAR(255) NOT NULL,
    account_number VARCHAR(50) NOT NULL,
    routing_number VARCHAR(20) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('CHECKING', 'SAVINGS')),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_method VARCHAR(30) DEFAULT 'IMMEDIATE' CHECK (verification_method IN ('IMMEDIATE', 'MICRO_DEPOSIT', 'MANUAL')),
    daily_transfer_limit DECIMAL(15, 2) DEFAULT 1000.00,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_external_accounts_customer ON external_accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_external_accounts_active ON external_accounts(is_active);

COMMENT ON TABLE external_accounts IS 'Stores external bank account information for transfers';

-- 2.7 Create scheduled_transactions table
CREATE TABLE IF NOT EXISTS scheduled_transactions (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    transaction_type VARCHAR(30) NOT NULL CHECK (transaction_type IN ('TRANSFER', 'BILL_PAYMENT')),
    from_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    to_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    external_account_id INTEGER REFERENCES external_accounts(id) ON DELETE SET NULL,
    payee_id INTEGER REFERENCES payees(id) ON DELETE SET NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    scheduled_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    frequency VARCHAR(20) CHECK (frequency IN ('WEEKLY', 'BIWEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')),
    next_execution_date DATE,
    end_date DATE,
    memo TEXT,
    status VARCHAR(30) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'EXECUTED', 'FAILED', 'CANCELLED', 'PAUSED')),
    execution_attempts INTEGER DEFAULT 0,
    last_execution_attempt TIMESTAMP,
    executed_transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scheduled_transactions_customer ON scheduled_transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_transactions_date ON scheduled_transactions(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_scheduled_transactions_status ON scheduled_transactions(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_transactions_type ON scheduled_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_scheduled_transactions_recurring ON scheduled_transactions(is_recurring);

COMMENT ON TABLE scheduled_transactions IS 'Stores scheduled and recurring transactions';

-- 2.8 Create transaction_limits table (for tracking daily limits)
CREATE TABLE IF NOT EXISTS transaction_limits (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    limit_date DATE NOT NULL,
    total_withdrawals DECIMAL(15, 2) DEFAULT 0.00,
    total_deposits DECIMAL(15, 2) DEFAULT 0.00,
    total_transfers DECIMAL(15, 2) DEFAULT 0.00,
    withdrawal_count INTEGER DEFAULT 0,
    deposit_count INTEGER DEFAULT 0,
    transfer_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, limit_date)
);

CREATE INDEX IF NOT EXISTS idx_transaction_limits_customer ON transaction_limits(customer_id);
CREATE INDEX IF NOT EXISTS idx_transaction_limits_account_date ON transaction_limits(account_id, limit_date);

COMMENT ON TABLE transaction_limits IS 'Tracks daily transaction limits per account';

-- 2.9 Create translations table for i18n
CREATE TABLE IF NOT EXISTS translations (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL,
    language VARCHAR(10) NOT NULL,
    value TEXT NOT NULL,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(key, language)
);

CREATE INDEX IF NOT EXISTS idx_translations_key ON translations(key);
CREATE INDEX IF NOT EXISTS idx_translations_language ON translations(language);
CREATE INDEX IF NOT EXISTS idx_translations_category ON translations(category);

COMMENT ON TABLE translations IS 'Stores UI text translations for internationalization';

-- ============================================================================
-- PART 3: INSERT SAMPLE/SEED DATA
-- ============================================================================

-- 3.1 Update existing customers with PIN hashes (for demo purposes)
-- Note: In production, PINs should be properly hashed using bcrypt
UPDATE customers 
SET pin_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYq7qO3iqxS', -- Hash for '1234'
    last_pin_change = CURRENT_TIMESTAMP
WHERE id = 1;

UPDATE customers 
SET pin_hash = '$2b$12$Uw5kEhBzhXNBJ/EQvkDcAu8qR8VQkzP5D8J5qVvN5k6JqY5bvZqCm', -- Hash for '5678'
    last_pin_change = CURRENT_TIMESTAMP
WHERE id = 2;

-- 3.2 Insert sample payees
INSERT INTO payees (customer_id, name, nickname, account_number, routing_number, category, is_active) VALUES
(1, 'Pacific Gas & Electric', 'PG&E', '123456789', '121000248', 'UTILITY', TRUE),
(1, 'Chase Credit Card', 'Chase CC', '9876543210123456', '021000021', 'CREDIT_CARD', TRUE),
(1, 'State Farm Insurance', 'Car Insurance', '555-123456', '062000019', 'INSURANCE', TRUE),
(2, 'AT&T', 'Phone Bill', '987654321', '121000248', 'PHONE', TRUE),
(2, 'Comcast', 'Internet', '456789123', '031201467', 'INTERNET', TRUE)
ON CONFLICT DO NOTHING;

-- 3.3 Insert sample external accounts
INSERT INTO external_accounts (customer_id, nickname, bank_name, account_number, routing_number, account_type, is_verified, verification_method, is_active) VALUES
(1, 'Chase Savings', 'Chase Bank', '9876543210', '021000021', 'SAVINGS', TRUE, 'IMMEDIATE', TRUE),
(1, 'Ally Checking', 'Ally Bank', '1234567890', '124003116', 'CHECKING', TRUE, 'IMMEDIATE', TRUE),
(2, 'Wells Fargo Savings', 'Wells Fargo', '5555666677', '121000248', 'SAVINGS', TRUE, 'IMMEDIATE', TRUE)
ON CONFLICT DO NOTHING;

-- 3.4 Insert base translations for English
INSERT INTO translations (key, language, value, category) VALUES
-- Authentication
('welcome.title', 'en', 'ATM Banking', 'auth'),
('welcome.subtitle', 'en', 'Select your preferred banking mode', 'auth'),
('language.select', 'en', 'Select Language', 'auth'),
('language.english', 'en', 'English', 'auth'),
('language.spanish', 'en', 'Spanish', 'auth'),
('pin.enter', 'en', 'Enter PIN', 'auth'),
('pin.confirm', 'en', 'Confirm', 'auth'),
('pin.cancel', 'en', 'Cancel', 'auth'),

-- Main Menu
('menu.title', 'en', 'Main Menu', 'menu'),
('menu.balance', 'en', 'Balance Inquiry', 'menu'),
('menu.withdrawal', 'en', 'Withdrawal', 'menu'),
('menu.cash_deposit', 'en', 'Cash Deposit', 'menu'),
('menu.check_deposit', 'en', 'Check Deposit', 'menu'),
('menu.transfer', 'en', 'Transfer', 'menu'),
('menu.bill_payment', 'en', 'Bill Payment', 'menu'),
('menu.change_pin', 'en', 'Change PIN', 'menu'),
('menu.mini_statement', 'en', 'Mini Statement', 'menu'),
('menu.exit', 'en', 'Exit', 'menu'),

-- Transactions
('transaction.account', 'en', 'Account', 'transaction'),
('transaction.amount', 'en', 'Amount', 'transaction'),
('transaction.from', 'en', 'From Account', 'transaction'),
('transaction.to', 'en', 'To Account', 'transaction'),
('transaction.memo', 'en', 'Memo', 'transaction'),
('transaction.confirm', 'en', 'Confirm', 'transaction'),
('transaction.cancel', 'en', 'Cancel', 'transaction'),
('transaction.success', 'en', 'Transaction Successful', 'transaction'),
('transaction.failed', 'en', 'Transaction Failed', 'transaction'),

-- Receipt
('receipt.preference', 'en', 'Receipt Preference', 'receipt'),
('receipt.none', 'en', 'No Receipt', 'receipt'),
('receipt.print', 'en', 'Print Receipt', 'receipt'),
('receipt.email', 'en', 'Email Receipt', 'receipt'),
('receipt.email_address', 'en', 'Email Address', 'receipt')

ON CONFLICT (key, language) DO NOTHING;

-- 3.5 Insert Spanish translations
INSERT INTO translations (key, language, value, category) VALUES
-- Authentication
('welcome.title', 'es', 'Banca ATM', 'auth'),
('welcome.subtitle', 'es', 'Seleccione su modo de banca preferido', 'auth'),
('language.select', 'es', 'Seleccionar Idioma', 'auth'),
('language.english', 'es', 'Inglés', 'auth'),
('language.spanish', 'es', 'Español', 'auth'),
('pin.enter', 'es', 'Ingrese PIN', 'auth'),
('pin.confirm', 'es', 'Confirmar', 'auth'),
('pin.cancel', 'es', 'Cancelar', 'auth'),

-- Main Menu
('menu.title', 'es', 'Menú Principal', 'menu'),
('menu.balance', 'es', 'Consulta de Saldo', 'menu'),
('menu.withdrawal', 'es', 'Retiro', 'menu'),
('menu.cash_deposit', 'es', 'Depósito en Efectivo', 'menu'),
('menu.check_deposit', 'es', 'Depósito de Cheque', 'menu'),
('menu.transfer', 'es', 'Transferencia', 'menu'),
('menu.bill_payment', 'es', 'Pago de Facturas', 'menu'),
('menu.change_pin', 'es', 'Cambiar PIN', 'menu'),
('menu.mini_statement', 'es', 'Mini Estado de Cuenta', 'menu'),
('menu.exit', 'es', 'Salir', 'menu'),

-- Transactions
('transaction.account', 'es', 'Cuenta', 'transaction'),
('transaction.amount', 'es', 'Monto', 'transaction'),
('transaction.from', 'es', 'De la Cuenta', 'transaction'),
('transaction.to', 'es', 'A la Cuenta', 'transaction'),
('transaction.memo', 'es', 'Nota', 'transaction'),
('transaction.confirm', 'es', 'Confirmar', 'transaction'),
('transaction.cancel', 'es', 'Cancelar', 'transaction'),
('transaction.success', 'es', 'Transacción Exitosa', 'transaction'),
('transaction.failed', 'es', 'Transacción Fallida', 'transaction'),

-- Receipt
('receipt.preference', 'es', 'Preferencia de Recibo', 'receipt'),
('receipt.none', 'es', 'Sin Recibo', 'receipt'),
('receipt.print', 'es', 'Imprimir Recibo', 'receipt'),
('receipt.email', 'es', 'Recibo por Correo', 'receipt'),
('receipt.email_address', 'es', 'Dirección de Correo', 'receipt')

ON CONFLICT (key, language) DO NOTHING;

-- ============================================================================
-- PART 4: CREATE VIEWS FOR REPORTING
-- ============================================================================

-- 4.1 View for customer transaction summary
CREATE OR REPLACE VIEW customer_transaction_summary AS
SELECT 
    c.id AS customer_id,
    c.name AS customer_name,
    COUNT(DISTINCT t.id) AS total_transactions,
    SUM(CASE WHEN t.operation = 'WITHDRAW' THEN t.amount ELSE 0 END) AS total_withdrawals,
    SUM(CASE WHEN t.operation IN ('DEPOSIT', 'CASH_DEPOSIT', 'CHECK_DEPOSIT') THEN t.amount ELSE 0 END) AS total_deposits,
    SUM(CASE WHEN t.operation = 'TRANSFER' THEN t.amount ELSE 0 END) AS total_transfers,
    SUM(CASE WHEN t.operation IN ('PAYMENT', 'BILL_PAYMENT') THEN t.amount ELSE 0 END) AS total_payments,
    MAX(t.timestamp) AS last_transaction_date
FROM customers c
LEFT JOIN accounts a ON a.customer_id = c.id
LEFT JOIN transactions t ON (t.from_account_id = a.id OR t.to_account_id = a.id)
WHERE t.status = 'COMPLETED'
GROUP BY c.id, c.name;

-- 4.2 View for daily transaction limits tracking
CREATE OR REPLACE VIEW daily_limits_status AS
SELECT 
    a.id AS account_id,
    a.account_number,
    a.type AS account_type,
    tl.limit_date,
    tl.total_withdrawals,
    a.daily_withdrawal_limit,
    (a.daily_withdrawal_limit - COALESCE(tl.total_withdrawals, 0)) AS remaining_withdrawal_limit,
    tl.total_deposits,
    a.daily_deposit_limit,
    (a.daily_deposit_limit - COALESCE(tl.total_deposits, 0)) AS remaining_deposit_limit,
    tl.total_transfers,
    a.daily_transfer_limit,
    (a.daily_transfer_limit - COALESCE(tl.total_transfers, 0)) AS remaining_transfer_limit
FROM accounts a
LEFT JOIN transaction_limits tl ON a.id = tl.account_id AND tl.limit_date = CURRENT_DATE;

-- 4.3 View for pending scheduled transactions
CREATE OR REPLACE VIEW pending_scheduled_transactions AS
SELECT 
    st.*,
    c.name AS customer_name,
    c.primary_email,
    fa.account_number AS from_account_number,
    ta.account_number AS to_account_number,
    ea.nickname AS external_account_nickname,
    p.name AS payee_name
FROM scheduled_transactions st
JOIN customers c ON st.customer_id = c.id
LEFT JOIN accounts fa ON st.from_account_id = fa.id
LEFT JOIN accounts ta ON st.to_account_id = ta.id
LEFT JOIN external_accounts ea ON st.external_account_id = ea.id
LEFT JOIN payees p ON st.payee_id = p.id
WHERE st.status = 'PENDING'
  AND st.scheduled_date <= CURRENT_DATE
ORDER BY st.scheduled_date, st.created_at;

-- ============================================================================
-- PART 5: CREATE FUNCTIONS/TRIGGERS FOR AUTOMATION
-- ============================================================================

-- 5.1 Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5.2 Apply updated_at trigger to relevant tables
DROP TRIGGER IF EXISTS update_customers_updated_at ON customers;
CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_accounts_updated_at ON accounts;
CREATE TRIGGER update_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_payees_updated_at ON payees;
CREATE TRIGGER update_payees_updated_at
    BEFORE UPDATE ON payees
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_external_accounts_updated_at ON external_accounts;
CREATE TRIGGER update_external_accounts_updated_at
    BEFORE UPDATE ON external_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_scheduled_transactions_updated_at ON scheduled_transactions;
CREATE TRIGGER update_scheduled_transactions_updated_at
    BEFORE UPDATE ON scheduled_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 5.3 Function to track daily transaction limits
CREATE OR REPLACE FUNCTION update_transaction_limits()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'COMPLETED' THEN
        -- Insert or update transaction limits for the day
        INSERT INTO transaction_limits (customer_id, account_id, limit_date, total_withdrawals, total_deposits, total_transfers, withdrawal_count, deposit_count, transfer_count)
        SELECT 
            a.customer_id,
            NEW.from_account_id,
            CURRENT_DATE,
            CASE WHEN NEW.operation = 'WITHDRAW' THEN NEW.amount ELSE 0 END,
            CASE WHEN NEW.operation IN ('DEPOSIT', 'CASH_DEPOSIT', 'CHECK_DEPOSIT') THEN NEW.amount ELSE 0 END,
            CASE WHEN NEW.operation = 'TRANSFER' THEN NEW.amount ELSE 0 END,
            CASE WHEN NEW.operation = 'WITHDRAW' THEN 1 ELSE 0 END,
            CASE WHEN NEW.operation IN ('DEPOSIT', 'CASH_DEPOSIT', 'CHECK_DEPOSIT') THEN 1 ELSE 0 END,
            CASE WHEN NEW.operation = 'TRANSFER' THEN 1 ELSE 0 END
        FROM accounts a
        WHERE a.id = NEW.from_account_id
        ON CONFLICT (account_id, limit_date)
        DO UPDATE SET
            total_withdrawals = transaction_limits.total_withdrawals + CASE WHEN NEW.operation = 'WITHDRAW' THEN NEW.amount ELSE 0 END,
            total_deposits = transaction_limits.total_deposits + CASE WHEN NEW.operation IN ('DEPOSIT', 'CASH_DEPOSIT', 'CHECK_DEPOSIT') THEN NEW.amount ELSE 0 END,
            total_transfers = transaction_limits.total_transfers + CASE WHEN NEW.operation = 'TRANSFER' THEN NEW.amount ELSE 0 END,
            withdrawal_count = transaction_limits.withdrawal_count + CASE WHEN NEW.operation = 'WITHDRAW' THEN 1 ELSE 0 END,
            deposit_count = transaction_limits.deposit_count + CASE WHEN NEW.operation IN ('DEPOSIT', 'CASH_DEPOSIT', 'CHECK_DEPOSIT') THEN 1 ELSE 0 END,
            transfer_count = transaction_limits.transfer_count + CASE WHEN NEW.operation = 'TRANSFER' THEN 1 ELSE 0 END;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5.4 Apply transaction limits trigger
DROP TRIGGER IF EXISTS track_transaction_limits ON transactions;
CREATE TRIGGER track_transaction_limits
    AFTER INSERT OR UPDATE ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_transaction_limits();

-- ============================================================================
-- PART 6: GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions on new tables to banking_user
GRANT ALL PRIVILEGES ON TABLE pin_history TO banking_user;
GRANT ALL PRIVILEGES ON TABLE payees TO banking_user;
GRANT ALL PRIVILEGES ON TABLE bill_payments TO banking_user;
GRANT ALL PRIVILEGES ON TABLE check_deposits TO banking_user;
GRANT ALL PRIVILEGES ON TABLE cash_deposits TO banking_user;
GRANT ALL PRIVILEGES ON TABLE external_accounts TO banking_user;
GRANT ALL PRIVILEGES ON TABLE scheduled_transactions TO banking_user;
GRANT ALL PRIVILEGES ON TABLE transaction_limits TO banking_user;
GRANT ALL PRIVILEGES ON TABLE translations TO banking_user;

-- Grant permissions on sequences
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO banking_user;

-- Grant permissions on views
GRANT SELECT ON customer_transaction_summary TO banking_user;
GRANT SELECT ON daily_limits_status TO banking_user;
GRANT SELECT ON pending_scheduled_transactions TO banking_user;

-- ============================================================================
-- PART 7: VERIFICATION QUERIES
-- ============================================================================

-- Run these queries to verify the migration was successful

-- Check new columns in existing tables
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'customers' 
  AND column_name IN ('pin_hash', 'pin_change_count', 'last_pin_change');

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'accounts' 
  AND column_name IN ('account_number', 'account_number_masked', 'daily_withdrawal_limit');

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'transactions' 
  AND column_name IN ('memo', 'receipt_mode', 'receipt_email');

-- Check new tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('pin_history', 'payees', 'bill_payments', 'check_deposits', 
                     'cash_deposits', 'external_accounts', 'scheduled_transactions', 
                     'transaction_limits', 'translations');

-- Check sample data
SELECT COUNT(*) as payee_count FROM payees;
SELECT COUNT(*) as external_account_count FROM external_accounts;
SELECT COUNT(*) as translation_count FROM translations;

-- Check views
SELECT viewname FROM pg_views WHERE schemaname = 'public' 
  AND viewname IN ('customer_transaction_summary', 'daily_limits_status', 'pending_scheduled_transactions');

-- ============================================================================
-- END OF MIGRATION SCRIPT
-- ============================================================================

-- To rollback this migration (use with caution in production):
/*
DROP VIEW IF EXISTS pending_scheduled_transactions CASCADE;
DROP VIEW IF EXISTS daily_limits_status CASCADE;
DROP VIEW IF EXISTS customer_transaction_summary CASCADE;
DROP TABLE IF EXISTS translations CASCADE;
DROP TABLE IF EXISTS transaction_limits CASCADE;
DROP TABLE IF EXISTS scheduled_transactions CASCADE;
DROP TABLE IF EXISTS external_accounts CASCADE;
DROP TABLE IF EXISTS cash_deposits CASCADE;
DROP TABLE IF EXISTS check_deposits CASCADE;
DROP TABLE IF EXISTS bill_payments CASCADE;
DROP TABLE IF EXISTS payees CASCADE;
DROP TABLE IF EXISTS pin_history CASCADE;

ALTER TABLE customers DROP COLUMN IF EXISTS pin_hash;
ALTER TABLE customers DROP COLUMN IF EXISTS pin_change_count;
ALTER TABLE customers DROP COLUMN IF EXISTS last_pin_change;
ALTER TABLE accounts DROP COLUMN IF EXISTS account_number;
ALTER TABLE accounts DROP COLUMN IF EXISTS account_number_masked;
ALTER TABLE accounts DROP COLUMN IF EXISTS daily_withdrawal_limit;
ALTER TABLE accounts DROP COLUMN IF EXISTS daily_deposit_limit;
ALTER TABLE accounts DROP COLUMN IF EXISTS daily_transfer_limit;
ALTER TABLE transactions DROP COLUMN IF EXISTS memo;
ALTER TABLE transactions DROP COLUMN IF EXISTS receipt_mode;
ALTER TABLE transactions DROP COLUMN IF EXISTS receipt_email;
ALTER TABLE transactions DROP COLUMN IF EXISTS is_scheduled;
ALTER TABLE transactions DROP COLUMN IF EXISTS scheduled_date;
*/