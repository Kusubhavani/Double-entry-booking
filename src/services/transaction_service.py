from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import uuid
import logging

from models.transaction import Transaction
from models.ledger_entry import LedgerEntry
from services.ledger_service import LedgerService
from services.account_service import AccountService

logger = logging.getLogger(__name__)


class TransactionService:
    @staticmethod
    def create_transaction(
        db: Session,
        transaction_type: str,
        amount: Decimal,
        currency: str = 'USD',
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """Create a new transaction record"""
        try:
            transaction_obj = Transaction(
                type=transaction_type,
                amount=amount,
                currency=currency,
                description=description,
                metadata=metadata or {},
                status='pending'
            )
            
            db.add(transaction_obj)
            db.flush()
            
            logger.info(f"Created transaction {transaction_obj.id} of type {transaction_type}")
            
            return transaction_obj
            
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
            raise
    
    @staticmethod
    def execute_transfer(
        db: Session,
        source_account_id: str,
        destination_account_id: str,
        amount: Decimal,
        currency: str = 'USD',
        description: Optional[str] = None
    ) -> Transaction:
        """Execute a transfer between two accounts with ACID compliance"""
        if source_account_id == destination_account_id:
            raise ValueError("Source and destination accounts cannot be the same")
        
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        
        try:
            # Check if accounts exist and are active
            source_account = AccountService.get_account(db, source_account_id)
            destination_account = AccountService.get_account(db, destination_account_id)
            
            if not source_account:
                raise ValueError("Source account does not exist")
            
            if source_account.status != 'active':
                raise ValueError("Source account is not active")
            
            if not destination_account:
                raise ValueError("Destination account does not exist")
            
            if destination_account.status != 'active':
                raise ValueError("Destination account is not active")
            
            # Check currency compatibility
            if source_account.currency != currency.upper():
                raise ValueError(f"Source account currency ({source_account.currency}) does not match transfer currency ({currency.upper()})")
            
            if destination_account.currency != currency.upper():
                raise ValueError(f"Destination account currency ({destination_account.currency}) does not match transfer currency ({currency.upper()})")
            
            # Calculate current balance with lock
            current_balance = LedgerService.calculate_balance(db, source_account_id)
            
            # Check for sufficient funds
            if current_balance < amount:
                raise ValueError(f"Insufficient funds. Available: {current_balance}, Required: {amount}")
            
            # Create transaction record
            transaction_obj = TransactionService.create_transaction(
                db=db,
                transaction_type='transfer',
                amount=amount,
                currency=currency,
                description=description,
                metadata={
                    'source_account_id': str(source_account_id),
                    'destination_account_id': str(destination_account_id)
                }
            )
            
            # Create ledger entries
            LedgerService.create_ledger_entries(
                db=db,
                transaction_id=transaction_obj.id,
                debit_account_id=source_account_id,
                credit_account_id=destination_account_id,
                amount=amount,
                description=description
            )
            
            # Verify double-entry balance
            if not LedgerService.verify_double_entry(db, transaction_obj.id):
                raise ValueError("Double-entry verification failed")
            
            # Update transaction status to completed
            transaction_obj.status = 'completed'
            transaction_obj.completed_at = datetime.utcnow()
            
            logger.info(f"Transfer completed successfully: {transaction_obj.id}")
            
            return transaction_obj
            
        except Exception as e:
            logger.error(f"Transfer failed: {str(e)}")
            raise
    
    @staticmethod
    def execute_deposit(
        db: Session,
        account_id: str,
        amount: Decimal,
        currency: str = 'USD',
        description: Optional[str] = None
    ) -> Transaction:
        """Execute a deposit (credit only)"""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        try:
            # Check if account exists and is active
            account = AccountService.get_account(db, account_id)
            
            if not account:
                raise ValueError("Account does not exist")
            
            if account.status != 'active':
                raise ValueError("Account is not active")
            
            if account.currency != currency.upper():
                raise ValueError(f"Account currency ({account.currency}) does not match deposit currency ({currency.upper()})")
            
            # Create transaction record
            transaction_obj = TransactionService.create_transaction(
                db=db,
                transaction_type='deposit',
                amount=amount,
                currency=currency,
                description=description,
                metadata={'account_id': str(account_id)}
            )
            
            # For deposit, we credit the account
            credit_entry = LedgerEntry(
                account_id=account_id,
                transaction_id=transaction_obj.id,
                entry_type='credit',
                amount=amount,
            )
            
            db.add(credit_entry)
            
            # Update transaction status
            transaction_obj.status = 'completed'
            transaction_obj.completed_at = datetime.utcnow()
            
            logger.info(f"Deposit completed successfully: {transaction_obj.id}")
            
            return transaction_obj
            
        except Exception as e:
            logger.error(f"Deposit failed: {str(e)}")
            raise
    
    @staticmethod
    def execute_withdrawal(
        db: Session,
        account_id: str,
        amount: Decimal,
        currency: str = 'USD',
        description: Optional[str] = None
    ) -> Transaction:
        """Execute a withdrawal (debit only)"""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        
        try:
            # Check if account exists and is active
            account = AccountService.get_account(db, account_id)
            
            if not account:
                raise ValueError("Account does not exist")
            
            if account.status != 'active':
                raise ValueError("Account is not active")
            
            if account.currency != currency.upper():
                raise ValueError(f"Account currency ({account.currency}) does not match withdrawal currency ({currency.upper()})")
            
            # Calculate current balance
            current_balance = LedgerService.calculate_balance(db, account_id)
            
            # Check for sufficient funds
            if current_balance < amount:
                raise ValueError(f"Insufficient funds. Available: {current_balance}, Required: {amount}")
            
            # Create transaction record
            transaction_obj = TransactionService.create_transaction(
                db=db,
                transaction_type='withdrawal',
                amount=amount,
                currency=currency,
                description=description,
                metadata={'account_id': str(account_id)}
            )
            
            # For withdrawal, we debit the account
            debit_entry = LedgerEntry(
                account_id=account_id,
                transaction_id=transaction_obj.id,
                entry_type='debit',
                amount=amount,
            )
            
            db.add(debit_entry)
            
            # Update transaction status
            transaction_obj.status = 'completed'
            transaction_obj.completed_at = datetime.utcnow()
            
            logger.info(f"Withdrawal completed successfully: {transaction_obj.id}")
            
            return transaction_obj
            
        except Exception as e:
            logger.error(f"Withdrawal failed: {str(e)}")
            raise
    
    @staticmethod
    def get_transaction(db: Session, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID"""
        try:
            return db.query(Transaction).filter(Transaction.id == transaction_id).first()
        except Exception as e:
            logger.error(f"Error getting transaction {transaction_id}: {e}")
            return None
