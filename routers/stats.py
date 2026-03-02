import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

import models, auth
from database import get_db

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
)

@router.get("/")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    
    total_products = db.query(models.Product).filter(models.Product.owner_id == user.id).count()
    low_stock_products = db.query(models.Product).filter(models.Product.stock < 10, models.Product.owner_id == user.id).count()
    
    # Calculate stock value based on buying_price, fallback to price (selling price) if none
    all_products = db.query(models.Product).filter(models.Product.owner_id == user.id).all()
    total_stock_value = sum((p.buying_price or p.price) * p.stock for p in all_products)
    
    bills = db.query(models.Bill).filter(models.Bill.owner_id == user.id).all()
    total_sales = sum(bill.total_amount for bill in bills)
    
    # Time-based sales
    today = datetime.utcnow().date()
    start_of_today = datetime(today.year, today.month, today.day)
    start_of_month = datetime(today.year, today.month, 1)
    
    todays_sales = sum(b.total_amount for b in bills if b.timestamp >= start_of_today)
    monthly_sales = sum(b.total_amount for b in bills if b.timestamp >= start_of_month)
    
    recent_sales = db.query(models.Bill).filter(models.Bill.owner_id == user.id).order_by(models.Bill.timestamp.desc()).limit(5).all()
    
    # 7-day sales trend
    today = datetime.utcnow().date()
    sales_by_date = { (today - timedelta(days=i)).strftime("%Y-%m-%d"): 0.0 for i in range(6, -1, -1) }
    
    seven_days_ago = today - timedelta(days=6)
    recent_bills = db.query(models.Bill).filter(
        models.Bill.timestamp >= datetime(seven_days_ago.year, seven_days_ago.month, seven_days_ago.day),
        models.Bill.owner_id == user.id
    ).all()
    
    for bill in recent_bills:
        date_str = bill.timestamp.strftime("%Y-%m-%d")
        if date_str in sales_by_date:
            sales_by_date[date_str] += bill.total_amount
            
    sales_trend = [{"name": date, "sales": amount} for date, amount in sales_by_date.items()]
    
    # Top 5 selling products
    product_sales = {}
    for bill in bills:
        for item in bill.cart_details:
            name = item.get("name", "Unknown Product")
            qty = item.get("qty", 0)
            if name in product_sales:
                product_sales[name] += qty
            else:
                product_sales[name] = qty
    
    top_products_sorted = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
    top_products = [{"name": name, "sold": qty} for name, qty in top_products_sorted]
    
    return {
        "total_products": total_products,
        "low_stock_products": low_stock_products,
        "total_sales": total_sales,
        "todays_sales": todays_sales,
        "monthly_sales": monthly_sales,
        "total_stock_value": total_stock_value,
        "sales_trend": sales_trend,
        "top_products": top_products,
        "recent_sales": [
            {
                "id": bill.id,
                "amount": bill.total_amount,
                "time": bill.timestamp,
                "cart_details": bill.cart_details
            } for bill in recent_sales
        ]
    }

@router.get("/download-report")
def download_report(db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    bills = db.query(models.Bill).filter(models.Bill.owner_id == user.id).order_by(models.Bill.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow(['Bill ID', 'Timestamp', 'Total Amount', 'Items Count', 'Summary'])
    
    for bill in bills:
        dt = bill.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        items_count = sum(item.get("qty", 0) for item in bill.cart_details)
        summary = ", ".join([f'{item.get("name", "Unknown")} (x{item.get("qty", 0)})' for item in bill.cart_details])
        writer.writerow([bill.id, dt, bill.total_amount, items_count, summary])
        
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales_report.csv"}
    )
