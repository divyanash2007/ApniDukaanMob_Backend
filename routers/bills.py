from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models, schemas, auth
from database import get_db

router = APIRouter(
    prefix="/bills",
    tags=["bills"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=schemas.BillResponse)
def create_bill(bill: schemas.BillCreate, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    new_bill = models.Bill(**bill.model_dump(), owner_id=user.id)
    db.add(new_bill)
    
    # Update inventory stock based on the bill
    for item in bill.cart_details:
        db_product = db.query(models.Product).filter(models.Product.barcode == item.get("barcode"), models.Product.owner_id == user.id).first()
        if db_product:
            db_product.stock = max(0, db_product.stock - item.get("qty", 0))
    
    db.commit()
    db.refresh(new_bill)
    return new_bill

@router.get("/", response_model=List[schemas.BillResponse])
def get_bills(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    return db.query(models.Bill).filter(models.Bill.owner_id == user.id).offset(skip).limit(limit).all()
