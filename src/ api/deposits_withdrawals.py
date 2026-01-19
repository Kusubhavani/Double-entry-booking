from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from decimal import Decimal
import uuid

from database import get_db
from services.transaction_service import TransactionService

router = APIRouter(prefix="", tags=["deposits", "withdrawals"])

class DepositRequest(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0, description="Deposit amount must be positive")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    description: str | None = Field(None, max_length=500)
    
    @validator('amount')
    def validate_amount(cls, v):
        amount_decimal = Decimal(str(v))
        if amount_decimal <= 0:
            raise ValueError("Amount must be positive")
        return amount_decimal

class WithdrawalRequest(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0, description="Withdrawal amount must be positive")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    description: str | None = Field(None, max_length=500)
    
    @validator('amount')
    def validate_amount(cls, v):
        amount_decimal = Decimal(str(v))
        if amount_decimal <= 0:
            raise ValueError("Amount must be positive")
        return amount_decimal

class TransactionResponse(BaseModel):
    id: str
    type: str
    status: str
    amount: float
    currency: str
    description: str | None
    created_at: str
    completed_at: str | None
    
    class Config:
        from_attributes = True

@router.post("/deposits", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_deposit(
    deposit_data: DepositRequest,
    db: Session = Depends(get_db)
):
    try:
        uuid.UUID(deposit_data.account_id)
        
        transaction = TransactionService.execute_deposit(
            db=db,
            account_id=deposit_data.account_id,
            amount=deposit_data.amount,
            currency=deposit_data.currency,
            description=deposit_data.description
        )
        
        return TransactionResponse(
            id=str(transaction.id),
            type=transaction.type,
            status=transaction.status,
            amount=float(transaction.amount),
            currency=transaction.currency,
            description=transaction.description,
            created_at=transaction.created_at.isoformat() if transaction.created_at else None,
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deposit failed: {str(e)}"
        )

@router.post("/withdrawals", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_withdrawal(
    withdrawal_data: WithdrawalRequest,
    db: Session = Depends(get_db)
):
    try:
        uuid.UUID(withdrawal_data.account_id)
        
        transaction = TransactionService.execute_withdrawal(
            db=db,
            account_id=withdrawal_data.account_id,
            amount=withdrawal_data.amount,
            currency=withdrawal_data.currency,
            description=withdrawal_data.description
        )
        
        return TransactionResponse(
            id=str(transaction.id),
            type=transaction.type,
            status=transaction.status,
            amount=float(transaction.amount),
            currency=transaction.currency,
            description=transaction.description,
            created_at=transaction.created_at.isoformat() if transaction.created_at else None,
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None
        )
        
    except ValueError as e:
        if "Insufficient funds" in str(e):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Withdrawal failed: {str(e)}"
        )
