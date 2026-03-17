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
    low_stock_products = db.query(models.Product).filter(models.Product.stock < 5, models.Product.owner_id == user.id).count()
    
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


@router.get("/insights")
def get_insights(date_range: str = "30d", db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    """
    Dynamic business insights endpoint.
    date_range options: '7d', '30d', '90d', '365d', 'all'
    """
    user = db.query(models.User).filter(models.User.username == current_user).first()
    today = datetime.utcnow().date()
    start_of_today = datetime(today.year, today.month, today.day)

    # --- Determine date range ---
    range_map = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}
    days_back = range_map.get(date_range, None)  # None means 'all'

    if days_back:
        range_start_date = today - timedelta(days=days_back - 1)
        range_start = datetime(range_start_date.year, range_start_date.month, range_start_date.day)
    else:
        range_start = datetime(2000, 1, 1)  # effectively 'all'

    # Fetch bills within the selected range
    range_bills = db.query(models.Bill).filter(
        models.Bill.owner_id == user.id,
        models.Bill.timestamp >= range_start
    ).order_by(models.Bill.timestamp.asc()).all()

    # ========== 1. SALES OVER TIME ==========
    sales_over_time = []

    if date_range == "365d" or date_range == "all":
        # Group by month
        monthly_sales = {}
        for bill in range_bills:
            key = bill.timestamp.strftime("%Y-%m")
            monthly_sales[key] = monthly_sales.get(key, 0) + bill.total_amount

        sorted_months = sorted(monthly_sales.keys())
        prev_val = 0
        for month_key in sorted_months:
            val = round(monthly_sales[month_key], 2)
            change = round(val - prev_val, 2)
            sales_over_time.append({
                "label": month_key,
                "sales": val,
                "change": change,
                "trend": "up" if change >= 0 else "down"
            })
            prev_val = val
    else:
        # Group by day
        num_days = days_back if days_back else 30
        date_map = {}
        for i in range(num_days - 1, -1, -1):
            d = today - timedelta(days=i)
            date_map[d.strftime("%Y-%m-%d")] = 0.0

        for bill in range_bills:
            key = bill.timestamp.strftime("%Y-%m-%d")
            if key in date_map:
                date_map[key] += bill.total_amount

        prev_val = 0
        for date_key, val in date_map.items():
            val = round(val, 2)
            change = round(val - prev_val, 2)
            sales_over_time.append({
                "label": date_key,
                "sales": val,
                "change": change,
                "trend": "up" if change >= 0 else "down"
            })
            prev_val = val

    # ========== 2. TOP SELLING PRODUCTS (from ALL bills) ==========
    all_bills = db.query(models.Bill).filter(models.Bill.owner_id == user.id).all()
    product_sales = {}
    product_revenue = {}
    for bill in all_bills:
        for item in bill.cart_details:
            name = item.get("name", "Unknown")
            qty = item.get("qty", 0)
            price = item.get("price", 0)
            product_sales[name] = product_sales.get(name, 0) + qty
            product_revenue[name] = product_revenue.get(name, 0) + (price * qty)

    top_products_sorted = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]
    top_products = [
        {"name": name, "sold": qty, "revenue": round(product_revenue.get(name, 0), 2)}
        for name, qty in top_products_sorted
    ]

    # ========== 3. DEAD STOCK ==========
    # Products that exist in inventory with stock > 0 but have NEVER been sold
    all_products = db.query(models.Product).filter(models.Product.owner_id == user.id).all()
    sold_product_names = set(product_sales.keys())

    dead_stock = []
    for p in all_products:
        if p.stock > 0 and p.name not in sold_product_names:
            dead_stock.append({
                "id": p.id,
                "name": p.name,
                "stock": p.stock,
                "value": round((p.buying_price or p.price) * p.stock, 2),
                "reason": "Never sold"
            })

    # Also check products that haven't sold in last 30 days
    thirty_days_ago = datetime(today.year, today.month, today.day) - timedelta(days=30)
    recent_bills_30d = db.query(models.Bill).filter(
        models.Bill.owner_id == user.id,
        models.Bill.timestamp >= thirty_days_ago
    ).all()
    recently_sold_names = set()
    for bill in recent_bills_30d:
        for item in bill.cart_details:
            recently_sold_names.add(item.get("name", ""))

    for p in all_products:
        if p.stock > 0 and p.name in sold_product_names and p.name not in recently_sold_names:
            # Was sold before but not in last 30 days
            if not any(d["id"] == p.id for d in dead_stock):
                dead_stock.append({
                    "id": p.id,
                    "name": p.name,
                    "stock": p.stock,
                    "value": round((p.buying_price or p.price) * p.stock, 2),
                    "reason": "No sales in 30 days"
                })

    # Sort dead stock by value (most capital locked up first)
    dead_stock.sort(key=lambda x: x["value"], reverse=True)

    # ========== 4. PEAK SALES HOURS ==========
    hour_sales = {h: 0.0 for h in range(24)}
    hour_count = {h: 0 for h in range(24)}
    for bill in all_bills:
        h = bill.timestamp.hour
        hour_sales[h] += bill.total_amount
        hour_count[h] += 1

    peak_hours = [
        {"hour": h, "sales": round(hour_sales[h], 2), "transactions": hour_count[h]}
        for h in range(24)
    ]

    # ========== 5. DAILY SUMMARY (Notification Data) ==========
    yesterday = today - timedelta(days=1)
    start_of_yesterday = datetime(yesterday.year, yesterday.month, yesterday.day)

    todays_total = sum(b.total_amount for b in all_bills if b.timestamp >= start_of_today)
    yesterdays_total = sum(b.total_amount for b in all_bills if start_of_yesterday <= b.timestamp < start_of_today)

    if yesterdays_total > 0:
        pct_change = round(((todays_total - yesterdays_total) / yesterdays_total) * 100, 1)
    elif todays_total > 0:
        pct_change = 100.0
    else:
        pct_change = 0.0

    daily_summary = {
        "todays_sales": round(todays_total, 2),
        "yesterdays_sales": round(yesterdays_total, 2),
        "change_amount": round(todays_total - yesterdays_total, 2),
        "change_percent": pct_change,
        "trend": "up" if todays_total >= yesterdays_total else "down"
    }

    return {
        "range": date_range,
        "sales_over_time": sales_over_time,
        "top_products": top_products,
        "dead_stock": dead_stock,
        "peak_hours": peak_hours,
        "daily_summary": daily_summary
    }
