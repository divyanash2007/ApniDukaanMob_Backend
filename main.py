from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

import models, schemas, auth
from database import engine, get_db
from routers import products, bills, stats, distributor_orders

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ApniDukaan Mobile API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:4173",
        "https://apnidukaan-lemon.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(bills.router)
app.include_router(stats.router)
app.include_router(distributor_orders.router)

# --- AUTHENTICATION ---
@app.post("/auth/signup", response_model=schemas.UserResponse, tags=["auth"])
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user_name = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user_name:
        raise HTTPException(status_code=400, detail="Shop name already registered")
        
    db_user_email = db.query(models.User).filter(models.User.business_email == user.business_email).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Business email already registered")
        
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, business_email=user.business_email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/login", tags=["auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form_data.username contains the email from the frontend
    user = db.query(models.User).filter(models.User.business_email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token = auth.create_refresh_token(data={"sub": user.username})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

import os
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
if not GOOGLE_CLIENT_ID:
    print("WARNING: GOOGLE_CLIENT_ID environment variable not set. Google Auth will fail.")

@app.post("/auth/google", tags=["auth"])
def google_auth(request: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        idinfo = id_token.verify_oauth2_token(request.token, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = idinfo.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Google token does not contain email")
            
        user = db.query(models.User).filter(models.User.business_email == email).first()
        if not user:
            # Create user
            username = email.split('@')[0]
            # Ensure unique username
            base_username = username
            counter = 1
            while db.query(models.User).filter(models.User.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1
                
            # Dummy password since it's google auth
            import secrets
            dummy_password = secrets.token_urlsafe(16)
            hashed_password = auth.get_password_hash(dummy_password)
            
            user = models.User(username=username, business_email=email, hashed_password=hashed_password)
            db.add(user)
            db.commit()
            db.refresh(user)
            
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        refresh_token = auth.create_refresh_token(data={"sub": user.username})
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

    except Exception as e:
        print(f"Google login error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google token")

@app.post("/auth/refresh", tags=["auth"])
def refresh_token(request: schemas.TokenRefreshRequest):
    payload = auth.decode_access_token(request.refresh_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )
    new_refresh_token = auth.create_refresh_token(data={"sub": username})
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserResponse, tags=["users"])
def read_users_me(current_user: str = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    # Since sub stores shopname (username), query by username
    user = db.query(models.User).filter(models.User.username == current_user).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/users/me", response_model=schemas.UserResponse, tags=["users"])
def update_user_me(user_update: schemas.UserUpdate, current_user: str = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user_update.username is not None and user_update.username != user.username:
        # Check if new username is taken
        existing = db.query(models.User).filter(models.User.username == user_update.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Shop name already taken")
        user.username = user_update.username
        
    if user_update.business_email is not None and user_update.business_email != user.business_email:
        # Check if new email is taken
        existing = db.query(models.User).filter(models.User.business_email == user_update.business_email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Business email already taken")
        user.business_email = user_update.business_email
        
    if user_update.password:
        if not user_update.old_password:
            raise HTTPException(status_code=400, detail="Current password is required to set a new password")
        if not auth.verify_password(user_update.old_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
            
        user.hashed_password = auth.get_password_hash(user_update.password)
        
    db.commit()
    db.refresh(user)
    return user
