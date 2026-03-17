from pydantic import BaseModel
from typing import Optional, List, Any
import datetime

class UserBase(BaseModel):
    username: str

class GoogleLoginRequest(BaseModel):
    token: str

class UserCreate(UserBase):
    business_email: str
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    business_email: Optional[str] = None
    password: Optional[str] = None
    old_password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    username: str
    business_email: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class ProductBase(BaseModel):
    barcode: str
    name: str
    price: float
    buying_price: Optional[float] = None
    mrp: Optional[float] = None
    gst: Optional[float] = None
    stock: int = 0
    distributor_info: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    class Config:
        from_attributes = True

class BillBase(BaseModel):
    total_amount: float
    cart_details: List[Any]

class BillCreate(BillBase):
    pass

class BillResponse(BillBase):
    id: int
    timestamp: datetime.datetime
    class Config:
        from_attributes = True

class DistributorOrderBase(BaseModel):
    order_details: List[Any]

class DistributorOrderCreate(DistributorOrderBase):
    pass

class DistributorOrderResponse(DistributorOrderBase):
    id: int
    timestamp: datetime.datetime
    status: str
    class Config:
        from_attributes = True
