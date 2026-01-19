import pytest
from decimal import Decimal
import uuid
from unittest.mock import patch

from services.account_service import AccountService
from services.transaction_service import TransactionService
from services.ledger_service import LedgerService
from models.account import Account
from models.transaction import Transaction
from models.ledger_entry import LedgerEntry

def test_create_account(db):
    """Test account creation"""
    account = AccountService.create_account(
        db=db,
        user_id="test_user_456",
        account_type="savings",
        currency="EUR"
    )
    
    assert account is not None
    assert account.user_id == "test_user_456"
    assert account.account_type == "savings"
    assert account.currency == "EUR"
    assert account.status == "active"
    
    # Verify it's saved in database
    saved_account = db.query(Account).filter(Account.id == account.id).first()
    assert saved_account is not None
    assert saved_account.user_id == "test_user_456"

def test_create_account_invalid_type(db):
    """Test account creation with invalid type"""
    with pytest.raises(ValueError, match="Account type must be one of"):
        AccountService.create_account(
            db=db,
            user_id="test_user",
            account_type="invalid_type",
            currency="USD"
        )

def test_create_account_invalid_currency(db):
    """Test account creation with invalid currency"""
    with pytest.raises(ValueError, match="Currency must be a 3-letter code"):
        AccountService.create_account(
            db=db,
            user_id="test_user",
            account_type="checking",
            currency="US"
        )

def test_get_account_with_balance(db):
    """Test getting account with balance calculation"""
    # Create account
    account = AccountService.create_account(
        db=db,
        user_id="test_user_balance",
        account_type="checking",
        currency="USD"
    )
    
    # Get account with balance (should be 0 initially)
    account_data = AccountService.get_account_with_balance(db, account.id)
    
    assert account_data is not None
    assert account_data['id'] == str(account.id)
    assert account_data['balance'] == 0.0

def test_calculate_balance(db):
    """Test balance calculation from ledger entries"""
    # Create accounts
    account1 = AccountService.create_account(
        db=db,
        user_id="user1",
        account_type="checking",
        currency="USD"
    )
    
    account2 = AccountService.create_account(
        db=db,
        user_id="user2",
        account_type="checking",
        currency="USD"
    )
    
    # Create transaction
    transaction = Transaction(
        type="transfer",
        amount=Decimal("150.75"),
        currency="USD",
        status="completed"
    )
    db.add(transaction)
    db.commit()
    
    # Create ledger entries
    debit_entry = LedgerEntry(
        account_id=account1.id,
        transaction_id=transaction.id,
        entry_type="debit",
        amount=Decimal("150.75")
    )
    
    credit_entry = LedgerEntry(
        account_id=account2.id,
        transaction_id=transaction.id,
        entry_type="credit",
        amount=Decimal("150.75")
    )
    
    db.add(debit_entry)
    db.add(credit_entry)
    db.commit()
    
    # Calculate balances
    balance1 = LedgerService.calculate_balance(db, account1.id)
    balance2 = LedgerService.calculate_balance(db, account2.id)
    
    assert balance1 == Decimal("-150.75")  # Debit reduces balance
    assert balance2 == Decimal("150.75")   # Credit increases balance

def test_execute_transfer_success(db):
    """Test successful transfer execution"""
    # Create source account with initial balance
    source_account = AccountService.create_account(
        db=db,
        user_id="sender",
        account_type="checking",
        currency="USD"
    )
    
    # Create destination account
    dest_account = AccountService.create_account(
        db=db,
        user_id="receiver",
        account_type="checking",
        currency="USD"
    )
    
    # Add initial balance to source account
    initial_deposit = Transaction(
        type="deposit",
        amount=Decimal("500.00"),
        currency="USD",
        status="completed"
    )
    db.add(initial_deposit)
    db.commit()
    
    credit_entry = LedgerEntry(
        account_id=source_account.id,
        transaction_id=initial_deposit.id,
        entry_type="credit",
        amount=Decimal("500.00")
    )
    db.add(credit_entry)
    db.commit()
    
    # Execute transfer
    transfer_amount = Decimal("200.00")
    transaction = TransactionService.execute_transfer(
        db=db,
        source_account_id=source_account.id,
        destination_account_id=dest_account.id,
        amount=transfer_amount,
        currency="USD",
        description="Test transfer"
    )
    
    # Verify transaction
    assert transaction is not None
    assert transaction.type == "transfer"
    assert transaction.status == "completed"
    assert transaction.amount == transfer_amount
    
    # Verify balances
    source_balance = LedgerService.calculate_balance(db, source_account.id)
    dest_balance = LedgerService.calculate_balance(db, dest_account.id)
    
    assert source_balance == Decimal("300.00")  # 500 - 200
    assert dest_balance == Decimal("200.00")    # 0 + 200

def test_execute_transfer_insufficient_funds(db):
    """Test transfer with insufficient funds"""
    # Create source account with no balance
    source_account = AccountService.create_account(
        db=db,
        user_id="sender",
        account_type="checking",
        currency="USD"
    )
    
    # Create destination account
    dest_account = AccountService.create_account(
        db=db,
        user_id="receiver",
        account_type="checking",
        currency="USD"
    )
    
    # Attempt transfer - should fail
    with pytest.raises(ValueError, match="Insufficient funds"):
        TransactionService.execute_transfer(
            db=db,
            source_account_id=source_account.id,
            destination_account_id=dest_account.id,
            amount=Decimal("100.00"),
            currency="USD"
        )

def test_execute_transfer_same_account(db):
    """Test transfer to same account"""
    account = AccountService.create_account(
        db=db,
        user_id="user",
        account_type="checking",
        currency="USD"
    )
    
    with pytest.raises(ValueError, match="Source and destination accounts cannot be the same"):
        TransactionService.execute_transfer(
            db=db,
            source_account_id=account.id,
            destination_account_id=account.id,
            amount=Decimal("100.00"),
            currency="USD"
        )

def test_execute_transfer_inactive_account(db):
    """Test transfer with inactive account"""
    # Create frozen source account
    source_account = AccountService.create_account(
        db=db,
        user_id="sender",
        account_type="checking",
        currency="USD"
    )
    source_account.status = "frozen"
    db.commit()
    
    # Create destination account
    dest_account = AccountService.create_account(
        db=db,
        user_id="receiver",
        account_type="checking",
        currency="USD"
    )
    
    with pytest.raises(ValueError, match="Source account is not active"):
        TransactionService.execute_transfer(
            db=db,
            source_account_id=source_account.id,
            destination_account_id=dest_account.id,
            amount=Decimal("100.00"),
            currency="USD"
        )

def test_execute_deposit_success(db):
    """Test successful deposit"""
    account = AccountService.create_account(
        db=db,
        user_id="user",
        account_type="checking",
        currency="USD"
    )
    
    deposit_amount = Decimal("300.50")
    transaction = TransactionService.execute_deposit(
        db=db,
        account_id=account.id,
        amount=deposit_amount,
        currency="USD",
        description="Salary deposit"
    )
    
    assert transaction is not None
    assert transaction.type == "deposit"
    assert transaction.status == "completed"
    assert transaction.amount == deposit_amount
    
    # Verify balance
    balance = LedgerService.calculate_balance(db, account.id)
    assert balance == deposit_amount

def test_execute_withdrawal_success(db):
    """Test successful withdrawal"""
    account = AccountService.create_account(
        db=db,
        user_id="user",
        account_type="checking",
        currency="USD"
    )
    
    # First deposit some money
    TransactionService.execute_deposit(
        db=db,
        account_id=account.id,
        amount=Decimal("500.00"),
        currency="USD"
    )
    
    # Then withdraw
    withdrawal_amount = Decimal("200.00")
    transaction = TransactionService.execute_withdrawal(
        db=db,
        account_id=account.id,
        amount=withdrawal_amount,
        currency="USD",
        description="ATM withdrawal"
    )
    
    assert transaction is not None
    assert transaction.type == "withdrawal"
    assert transaction.status == "completed"
    assert transaction.amount == withdrawal_amount
    
    # Verify balance
    balance = LedgerService.calculate_balance(db, account.id)
    assert balance == Decimal("300.00")  # 500 - 200

def test_execute_withdrawal_insufficient_funds(db):
    """Test withdrawal with insufficient funds"""
    account = AccountService.create_account(
        db=db,
        user_id="user",
        account_type="checking",
        currency="USD"
    )
    
    with pytest.raises(ValueError, match="Insufficient funds"):
        TransactionService.execute_withdrawal(
            db=db,
            account_id=account.id,
            amount=Decimal("100.00"),
            currency="USD"
        )

def test_concurrent_transfers(db):
    """Test concurrent transfer requests"""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    
    # Create accounts
    source_account = AccountService.create_account(
        db=db,
        user_id="sender",
        account_type="checking",
        currency="USD"
    )
    
    dest_account = AccountService.create_account(
        db=db,
        user_id="receiver",
        account_type="checking",
        currency="USD"
    )
    
    # Add initial balance
    TransactionService.execute_deposit(
        db=db,
        account_id=source_account.id,
        amount=Decimal("1000.00"),
        currency="USD"
    )
    
    # Function to execute transfer
    def make_transfer(amount):
        with db.begin():
            try:
                TransactionService.execute_transfer(
                    db=db,
                    source_account_id=source_account.id,
                    destination_account_id=dest_account.id,
                    amount=Decimal(str(amount)),
                    currency="USD"
                )
                return True
            except Exception:
                return False
    
    # Execute concurrent transfers
    amounts = [100.00, 200.00, 300.00, 400.00]  # Total: 1000
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(make_transfer, amounts))
    
    # Verify all transfers completed
    assert all(results) == True
    
    # Verify final balances
    source_balance = LedgerService.calculate_balance(db, source_account.id)
    dest_balance = LedgerService.calculate_balance(db, dest_account.id)
    
    assert source_balance == Decimal("0.00")  # All money transferred
    assert dest_balance == Decimal("1000.00")  # All money received

def test_get_account_ledger(db):
    """Test retrieving account ledger"""
    account = AccountService.create_account(
        db=db,
        user_id="ledger_user",
        account_type="checking",
        currency="USD"
    )
    
    # Create multiple transactions
    TransactionService.execute_deposit(
        db=db,
        account_id=account.id,
        amount=Decimal("100.00"),
        currency="USD"
    )
    
    TransactionService.execute_withdrawal(
        db=db,
        account_id=account.id,
        amount=Decimal("30.00"),
        currency="USD"
    )
    
    # Get ledger
    ledger_entries = LedgerService.get_account_ledger(db, account.id)
    
    assert len(ledger_entries) == 2
    assert ledger_entries[0].entry_type == "debit"  # Withdrawal (most recent)
    assert ledger_entries[1].entry_type == "credit"  # Deposit

def test_verify_double_entry_balance(db):
    """Test double-entry bookkeeping verification"""
    account1 = AccountService.create_account(
        db=db,
        user_id="user1",
        account_type="checking",
        currency="USD"
    )
    
    account2 = AccountService.create_account(
        db=db,
        user_id="user2",
        account_type="checking",
        currency="USD"
    )
    
    # Execute transfer
    transaction = TransactionService.execute_transfer(
        db=db,
        source_account_id=account1.id,
        destination_account_id=account2.id,
        amount=Decimal("250.00"),
        currency="USD"
    )
    
    # Verify double-entry balance
    is_balanced = LedgerService.verify_double_entry_balance(db, transaction.id)
    assert is_balanced == True
