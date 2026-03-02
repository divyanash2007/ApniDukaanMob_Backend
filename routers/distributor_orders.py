from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models, schemas, auth
from database import get_db

router = APIRouter(
    prefix="/distributor_orders",
    tags=["distributor_orders"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=schemas.DistributorOrderResponse)
def create_order(order: schemas.DistributorOrderCreate, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    new_order = models.DistributorOrder(**order.model_dump(), owner_id=user.id)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order

@router.get("/pending", response_model=schemas.DistributorOrderResponse)
def get_pending_order(db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    pending_order = db.query(models.DistributorOrder).filter(
        models.DistributorOrder.owner_id == user.id,
        models.DistributorOrder.status == "PENDING"
    ).order_by(models.DistributorOrder.timestamp.desc()).first()
    
    if not pending_order:
        raise HTTPException(status_code=404, detail="No pending orders found")
        
    return pending_order

@router.get("/last", response_model=schemas.DistributorOrderResponse)
def get_last_order(db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    last_order = db.query(models.DistributorOrder).filter(
        models.DistributorOrder.owner_id == user.id
    ).order_by(models.DistributorOrder.timestamp.desc()).first()
    
    if not last_order:
        raise HTTPException(status_code=404, detail="No orders found")
        
    return last_order

@router.put("/{order_id}/deliver", response_model=schemas.DistributorOrderResponse)
def mark_order_delivered(order_id: int, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    order = db.query(models.DistributorOrder).filter(
        models.DistributorOrder.id == order_id, 
        models.DistributorOrder.owner_id == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if order.status == "DELIVERED":
        raise HTTPException(status_code=400, detail="Order is already delivered")
        
    # Update inventory
    for item in order.order_details:
        db_product = db.query(models.Product).filter(
            models.Product.barcode == item.get("barcode"), 
            models.Product.owner_id == user.id
        ).first()
        if db_product:
            db_product.stock += item.get("qty", 0)
            
    order.status = "DELIVERED"
    db.commit()
    db.refresh(order)
    return order
