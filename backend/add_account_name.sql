-- Add account_name column to accounts table
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_name VARCHAR(100);

-- Update existing accounts with sample names
UPDATE accounts SET account_name = 'My Checking' WHERE id = 1 AND account_name IS NULL;
UPDATE accounts SET account_name = 'Emergency Fund' WHERE id = 2 AND account_name IS NULL;
UPDATE accounts SET account_name = 'Cuenta Corriente' WHERE id = 3 AND account_name IS NULL;
UPDATE accounts SET account_name = 'Ahorros' WHERE id = 4 AND account_name IS NULL;
