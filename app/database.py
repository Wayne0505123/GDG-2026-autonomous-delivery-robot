from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# 1. 讀取環境變數 (對應 docker-compose.yml 裡的 DATABASE_URL)
# 如果沒讀到 (例如你在本機直接跑 python main.py)，就用預設值連 localhost:5433
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://robot_user:robot_pass@localhost:5433/robot_db")

# 2. 建立資料庫引擎
engine = create_engine(DATABASE_URL)

# 3. 建立 Session 工廠 (之後每個 Request 都會跟它要連線)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 宣告 ORM 基底類別 (之後你的 Model 都要繼承它)
Base = declarative_base()

# 5. Dependency (給 API 用的工具函式)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()