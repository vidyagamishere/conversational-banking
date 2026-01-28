-- Migration: Add cards table to map card numbers (track2 data) to customers
-- Date: 2026-01-25
-- Description: Creates cards table to properly link card numbers with customers and their accounts

-- Create cards table
CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    card_number VARCHAR(20) NOT NULL UNIQUE,
    card_number_masked VARCHAR(20) NOT NULL,
    card_type VARCHAR(20) DEFAULT 'DEBIT' CHECK (card_type IN ('DEBIT', 'CREDIT', 'PREPAID')),
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'BLOCKED', 'EXPIRED', 'LOST', 'STOLEN')),
    expiry_date VARCHAR(4),  -- MMYY format
    issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_cards_customer ON cards(customer_id);
CREATE INDEX IF NOT EXISTS idx_cards_number ON cards(card_number);
CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status);

-- Insert sample cards for existing customers
-- Customer 1: John Doe (assuming customer_id = 1)
INSERT INTO cards (customer_id, card_number, card_number_masked, card_type, status, expiry_date)
VALUES 
    (1, '4111111111111111', '****1111', 'DEBIT', 'ACTIVE', '1228'),
    (2, '4222222222222222', '****2222', 'DEBIT', 'ACTIVE', '0630')
ON CONFLICT (card_number) DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE cards IS 'Maps card numbers (Track2 data) to customers';
COMMENT ON COLUMN cards.card_number IS 'Full PAN/Track2 card number - encrypted in production';
COMMENT ON COLUMN cards.card_number_masked IS 'Masked card number for display (e.g., ****1234)';
COMMENT ON COLUMN cards.card_type IS 'Type of card: DEBIT, CREDIT, or PREPAID';
COMMENT ON COLUMN cards.status IS 'Card status: ACTIVE, BLOCKED, EXPIRED, LOST, or STOLEN';
COMMENT ON COLUMN cards.expiry_date IS 'Card expiration date in MMYY format';
