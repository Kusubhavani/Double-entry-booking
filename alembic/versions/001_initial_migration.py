"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE account_type_enum AS ENUM ('checking', 'savings', 'business');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE account_status_enum AS ENUM ('active', 'frozen', 'closed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE transaction_type_enum AS ENUM ('transfer', 'deposit', 'withdrawal');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE transaction_status_enum AS ENUM ('pending', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE entry_type_enum AS ENUM ('debit', 'credit');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create accounts table
    op.create_table('accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('account_type', sa.Enum('checking', 'savings', 'business', name='account_type_enum'), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('status', sa.Enum('active', 'frozen', 'closed', name='account_status_enum'), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='currency_check'),
        comment='Financial accounts for users'
    )
    
    # Create indexes for accounts
    op.create_index(op.f('ix_accounts_user_id'), 'accounts', ['user_id'], unique=False)
    
    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('type', sa.Enum('transfer', 'deposit', 'withdrawal', name='transaction_type_enum'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'completed', 'failed', name='transaction_status_enum'), nullable=False, server_default='pending'),
        sa.Column('amount', sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('amount > 0', name='positive_amount'),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='transaction_currency_check'),
        comment='Financial transactions'
    )
    
    # Create indexes for transactions
    op.create_index(op.f('ix_transactions_status'), 'transactions', ['status'], unique=False)
    op.create_index(op.f('ix_transactions_created_at'), 'transactions', ['created_at'], unique=False)
    
    # Create ledger_entries table
    op.create_table('ledger_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entry_type', sa.Enum('debit', 'credit', name='entry_type_enum'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], name='ledger_entries_account_id_fkey', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name='ledger_entries_transaction_id_fkey', ondelete='RESTRICT'),
        sa.CheckConstraint('amount > 0', name='positive_ledger_amount'),
        sa.UniqueConstraint('transaction_id', 'account_id', 'entry_type', name='unique_transaction_account_entry'),
        comment='Double-entry ledger entries'
    )
    
    # Create indexes for ledger_entries
    op.create_index(op.f('ix_ledger_entries_account_id'), 'ledger_entries', ['account_id'], unique=False)
    op.create_index(op.f('ix_ledger_entries_transaction_id'), 'ledger_entries', ['transaction_id'], unique=False)
    op.create_index(op.f('ix_ledger_entries_created_at'), 'ledger_entries', ['created_at'], unique=False)
    
    # Create function for updating updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Create trigger for accounts
    op.execute("""
        CREATE TRIGGER update_accounts_updated_at
            BEFORE UPDATE ON accounts
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_accounts_updated_at ON accounts;")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column;")
    
    # Drop tables in reverse order
    op.drop_table('ledger_entries')
    op.drop_table('transactions')
    op.drop_table('accounts')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS entry_type_enum;")
    op.execute("DROP TYPE IF EXISTS transaction_status_enum;")
    op.execute("DROP TYPE IF EXISTS transaction_type_enum;")
    op.execute("DROP TYPE IF EXISTS account_status_enum;")
    op.execute("DROP TYPE IF EXISTS account_type_enum;")
