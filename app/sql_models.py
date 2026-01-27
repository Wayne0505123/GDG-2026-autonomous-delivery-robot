from sqlalchemy import Column, Integer, String, DateTime, Float, JSON
from .database import Base
from datetime import datetime

# 1. 使用者模型 (對應 main.py 的 import User)
class User(Base):
    __tablename__ = "users"

    email = Column(String, primary_key=True, index=True)
    username = Column(String)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# 2. 訂單模型 (補齊了所有 main.py 會用到的欄位)
class OrderDB(Base):
    __tablename__ = "orders" # 資料庫裡的表格名稱

    # 基本資訊
    id = Column(String, primary_key=True, index=True) # 對應 order_id
    map_id = Column(String, index=True)
    status = Column(String, default="CREATED") # 對應 state
    created_at = Column(DateTime, default=datetime.utcnow)

    # 導航數據
    total_distance_cm = Column(Float)
    eta_sec = Column(Float)
    route = Column(JSON)  # 👈 關鍵！用來存路徑陣列 [node1, node2...]

    # 訂單商業邏輯 (對應 fake_orders_db 的欄位)
    user_email = Column(String, index=True)
    store_name = Column(String)
    items = Column(JSON)  # 👈 關鍵！用來存商品列表 [{"name": "..", "price": 10}]
    total_amount = Column(Float) # 對應 total