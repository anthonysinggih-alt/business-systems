from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# ---------------- PRODUCTS DATABASE ----------------
ProductBase = declarative_base()
product_engine = create_engine("sqlite:///products.db", connect_args={"check_same_thread": False})
ProductSession = sessionmaker(bind=product_engine)

class Product(ProductBase):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    product_id = Column(String, unique=True)  # e.g., "P001"
    product_name = Column(String)
    unit_price = Column(Float)

ProductBase.metadata.create_all(product_engine)

# ---------------- TRANSACTIONS DATABASE ----------------
TransactionBase = declarative_base()
transaction_engine = create_engine("sqlite:///transactions.db", connect_args={"check_same_thread": False})
TransactionSession = sessionmaker(bind=transaction_engine)

class Transaction(TransactionBase):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    transaction_date = Column(DateTime, default=datetime.now)
    items = Column(Text)
    subtotal = Column(Float)
    tax = Column(Float, default=0.0)
    service_charge = Column(Float, default=0.0)
    total = Column(Float)
    payment_amount = Column(Float)
    change_amount = Column(Float)
    payment_type = Column(String, default="Cash")

TransactionBase.metadata.create_all(transaction_engine)

# ---------------- PENDING TRANSACTION (CART) DATABASE ----------------
CartBase = declarative_base()
cart_engine = create_engine("sqlite:///cart.db", connect_args={"check_same_thread": False})
CartSession = sessionmaker(bind=cart_engine)

class CartItem(CartBase):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True)
    product_id = Column(String)
    product_name = Column(String)
    unit_price = Column(Float)
    quantity = Column(Integer)
    session_id = Column(String, default="current")  # Allows multiple carts if needed

CartBase.metadata.create_all(cart_engine)