from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # Shop name
    business_email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    has_lifetime_subscription = Column(Boolean, default=False)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String, index=True)
    name = Column(String, index=True)
    price = Column(Float) # selling price
    buying_price = Column(Float, nullable=True)
    mrp = Column(Float, nullable=True)
    gst = Column(Float, nullable=True)
    stock = Column(Integer, default=0)
    distributor_info = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)

class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    total_amount = Column(Float)
    cart_details = Column(JSON) # Store list of products and QTY
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)

class DistributorOrder(Base):
    __tablename__ = "distributor_orders"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="PENDING") # PENDING, DELIVERED
    order_details = Column(JSON) # Store ordered product info and qty
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
