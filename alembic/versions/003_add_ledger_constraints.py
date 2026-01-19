"""Add ledger constraints and audit columns

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add audit columns to transactions
    op.add_column('transactions', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('transactions', sa.Column('updated_by', sa.String(length=255), nullable=True))
    
    # Add check constraint for currency consistency in transfers
    op.execute("""
        ALTER TABLE transactions
        ADD CONSTRAINT transfer_currency_check 
        CHECK (
            (type != 'transfer') OR 
            (
                metadata IS NOT NULL AND 
                metadata->>'source_account_id' IS NOT NULL AND 
                metadata->>'destination_account_id' IS NOT NULL
            )
        )
    """)
    
    # Create function to check double-entry balance
    op.execute("""
        CREATE OR REPLACE FUNCTION check_double_entry_balance()
        RETURNS TRIGGER AS $$
        DECLARE
            total_balance NUMERIC(19,4);
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- Check that sum of credits - debits = 0 for the transaction
                SELECT COALESCE(SUM(
                    CASE 
                        WHEN entry_type = 'credit' THEN amount
                        WHEN entry_type = 'debit' THEN -amount
                    END
                ), 0) INTO total_balance
                FROM ledger_entries
                WHERE transaction_id = NEW.transaction_id;
                
                IF total_balance != 0 THEN
                    RAISE EXCEPTION 'Double-entry balance violation: Total balance must be 0, got %', total_balance;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for ledger entries
    op.execute("""
        CREATE CONSTRAINT TRIGGER enforce_double_entry_balance
        AFTER INSERT ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION check_double_entry_balance();
    """)
    
    # Create view for account balances
    op.execute("""
        CREATE OR REPLACE VIEW account_balances AS
        SELECT 
            a.id as account_id,
            a.user_id,
            a.account_type,
            a.currency,
            a.status,
            COALESCE(SUM(
                CASE 
                    WHEN le.entry_type = 'credit' THEN le.amount
                    WHEN le.entry_type = 'debit' THEN -le.amount
                END
            ), 0) as current_balance,
            COUNT(le.id) as total_entries,
            MAX(le.created_at) as last_transaction_date
        FROM accounts a
        LEFT JOIN ledger_entries le ON a.id = le.account_id
        GROUP BY a.id, a.user_id, a.account_type, a.currency, a.status;
    """)
    
    # Create materialized view for daily balances (for reporting)
    op.execute("""
        CREATE MATERIALIZED VIEW daily_account_balances AS
        SELECT 
            DATE(le.created_at) as balance_date,
            le.account_id,
            COALESCE(SUM(
                CASE 
                    WHEN le.entry_type = 'credit' THEN le.amount
                    WHEN le.entry_type = 'debit' THEN -le.amount
                END
            ), 0) as daily_balance
        FROM ledger_entries le
        GROUP BY DATE(le.created_at), le.account_id
        ORDER BY balance_date DESC;
    """)
    
    # Create index on materialized view
    op.execute("""
        CREATE UNIQUE INDEX idx_daily_balances_date_account 
        ON daily_account_balances(balance_date, account_id);
    """)


def downgrade() -> None:
    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_account_balances;")
    
    # Drop view
    op.execute("DROP VIEW IF EXISTS account_balances;")
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS enforce_double_entry_balance ON ledger_entries;")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS check_double_entry_balance;")
    
    # Drop constraint
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transfer_currency_check;")
    
    # Drop columns
    op.drop_column('transactions', 'updated_by')
    op.drop_column('transactions', 'version')
