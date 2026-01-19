from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from decimal import Decimal
import uuid

from database import get_db
from services.transaction_service import TransactionService

router = APIRouter(prefix="/transfers", tags=["transfers"])


class TransferRequest(BaseModel):
    source_account_id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    destination_account_id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174001")
    amount: float = Field(..., gt=0, description="Transfer amount must be positive", example=100.50)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$", example="USD")
    description: str | None = Field(None, max_length=500, example="Payment for services")
    
    @validator('amount')
    def validate_amount(cls, v):
        # Convert to Decimal for precise arithmetic
        try:
            amount_decimal = Decimal(str(v))
            if amount_decimal <= 0:
                raise ValueError("Amount must be positive")
            return amount_decimal
        except Exception:
            raise ValueError("Invalid amount format")


class TransactionResponse(BaseModel):
    id: str
    type: str
    status: str
    amount: float
    currency: str
    description: str | None
    metadata: dict
    created_at: str
    completed_at: str | None
    
    class Config:
        from_attributes = True


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    transfer_data: TransferRequest,
    db: Session = Depends(get_db)
):
    """Execute a transfer between accounts"""
    try:
        # Validate UUIDs
        uuid.UUID(transfer_data.source_account_id)
        uuid.UUID(transfer_data.destination_account_id)
        
        transaction = TransactionService.execute_transfer(
            db=db,
            source_account_id=transfer_data.source_account_id,
            destination_account_id=transfer_data.destination_account_id,
            amount=transfer_data.amount,
            currency=transfer_data.currency,
            description=transfer_data.description
        )
        
        return TransactionResponse(
            id=str(transaction.id),
            type=transaction.type,
            status=transaction.status,
            amount=float(transaction.amount),
            currency=transaction.currency,
            description=transaction.description,
            metadata=transaction.metadata or {},
            created_at=transaction.created_at.isoformat() if transaction.created_at else None,
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None
        )
        
    except ValueError as e:
        error_message = str(e)
        if "Insufficient funds" in error_message:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_message
            )
        elif "not active" in error_message.lower() or "does not exist" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer failed: {str(e)}"
        )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transfer(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """Get transfer details"""
    try:
        # Validate UUID
        uuid.UUID(transaction_id)
        
        transaction = TransactionService.get_transaction(db, transaction_id)
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        return TransactionResponse(
            id=str(transaction.id),
            type=transaction.type,
            status=transaction.status,
            amount=float(transaction.amount),
            currency=transaction.currency,
            description=transaction.description,
            metadata=transaction.metadata or {},
            created_at=transaction.created_at.isoformat() if transaction.created_at else None,
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transaction ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transaction: {str(e)}"
        )
