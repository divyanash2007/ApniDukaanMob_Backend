import os
import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import models, schemas, auth
from database import get_db

router = APIRouter(
    prefix="/payment",
    tags=["payment"],
)

# Initialize Razorpay Client
razorpay_key_id = os.environ.get("RAZORPAY_KEY_ID")
razorpay_key_secret = os.environ.get("RAZORPAY_KEY_SECRET")

client = None
if razorpay_key_id and razorpay_key_secret:
    client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))
else:
    print("WARNING: Razorpay keys not found in environment. Payments will fail.")

@router.post("/create-order")
def create_order(request: schemas.PaymentOrderRequest, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured")

    payment_data = {
        "amount": int(request.amount * 100),  # Amount in paise
        "currency": "INR",
        "receipt": f"receipt_{user.id}_{os.urandom(4).hex()}",
        "notes": {
            "user_id": user.id,
            "purpose": "Lifetime Subscription"
        }
    }

    try:
        razorpay_order = client.order.create(data=payment_data)
        return {"order_id": razorpay_order["id"], "amount": razorpay_order["amount"], "currency": razorpay_order["currency"]}
    except Exception as e:
        print(f"Razorpay order creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment order")

@router.post("/verify")
def verify_payment(request: schemas.PaymentVerifyRequest, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured")

    # Verify signature
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': request.razorpay_order_id,
            'razorpay_payment_id': request.razorpay_payment_id,
            'razorpay_signature': request.razorpay_signature
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Payment Signature")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Payment verified successfully, activate lifetime subscription
    user.has_lifetime_subscription = True
    db.commit()
    db.refresh(user)

    return {"message": "Payment successful", "has_lifetime_subscription": user.has_lifetime_subscription}
