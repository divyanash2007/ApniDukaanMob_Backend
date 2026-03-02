from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
import csv
import io

import models, schemas, auth
from database import get_db

router = APIRouter(
    prefix="/products",
    tags=["products"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[schemas.ProductResponse])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    return db.query(models.Product).filter(models.Product.owner_id == user.id).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.ProductResponse)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    db_product = db.query(models.Product).filter(models.Product.barcode == product.barcode, models.Product.owner_id == user.id).first()
    if db_product:
        raise HTTPException(status_code=400, detail="Product with this barcode already exists in your inventory")
    new_product = models.Product(**product.model_dump(), owner_id=user.id)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@router.put("/{product_id}", response_model=schemas.ProductResponse)
def update_product(product_id: int, product: schemas.ProductBase, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    db_product = db.query(models.Product).filter(models.Product.id == product_id, models.Product.owner_id == user.id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in product.model_dump().items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    db_product = db.query(models.Product).filter(models.Product.id == product_id, models.Product.owner_id == user.id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted successfully"}

@router.post("/bulk-upload/")
async def bulk_upload_products(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    
    content = await file.read()
    try:
        decoded_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded_content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV. Error: {str(e)}")
    
    # Required keys
    required_keys = ['barcode', 'name', 'price', 'stock']
    if not csv_reader.fieldnames or not all(key in csv_reader.fieldnames for key in required_keys):
        raise HTTPException(status_code=400, detail="Invalid CSV format.")

    added = 0
    updated = 0
    errors = []

    for idx, row in enumerate(csv_reader, start=2):
        barcode = row.get('barcode', '').strip()
        name = row.get('name', '').strip()
        
        try:
            price = float(row.get('price', 0))
            stock = int(row.get('stock', 0))
            
            if not barcode or not name:
                continue
                
            db_product = db.query(models.Product).filter(models.Product.barcode == barcode, models.Product.owner_id == user.id).first()
            if db_product:
                db_product.name = name
                db_product.price = price
                db_product.stock += stock
                updated += 1
            else:
                new_product = models.Product(
                    barcode=barcode,
                    name=name,
                    price=price,
                    stock=stock,
                    owner_id=user.id
                )
                db.add(new_product)
                added += 1
                
        except ValueError:
            errors.append(f"Row {idx}: Invalid numeric format.")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error saving products")
        
    return {"status": "success", "added": added, "updated": updated, "errors": errors}
