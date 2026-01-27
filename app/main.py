from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
import uuid
import json
from pathlib import Path
from datetime import datetime
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db

# 1. 資料庫相關 Import
from .database import engine, Base
# ⚠️ 注意：需確認你的 sql_models.py 已經建立，且裡面有 User 和 OrderDB
from .sql_models import User, OrderDB 

# 2. Pydantic Models & Logic Import
from .models import MapData, CreateOrderReq, CreateOrderResp
from .graph import build_graph, dijkstra, astar
from .services import estimate_eta_sec
from .state import MAP_STORE, GRAPH_STORE, ORDER_STORE, fake_orders_db

# 3. Router Import
from .routers import stores, products, auth, users, cart
from .ws import ws_router

app = FastAPI(title="ESP32 Car Backend")

# --- CORS 設定 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 掛載路由 (集中在這裡就好，不要重複) ---
app.include_router(auth.router)      # 登入註冊
app.include_router(users.router)     # 使用者資訊
app.include_router(stores.router)    # 商店
app.include_router(products.router)  # 商品
app.include_router(ws_router)        # WebSocket
# app.include_router(cart.router)    # 購物車 (還沒寫好 cart.py 前先註解)


# ===============================
# 輔助函式: 載入地圖 logic
# ===============================
def load_map_logic(path: str = "data/map.json"):
    """讀取 JSON 並建立 Graph 的核心邏輯"""
    try:
        print(f"📍 Loading map from: {path}")
        if not Path(path).exists():
            print(f"⚠️ Map file not found: {path}")
            return

        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        map_data = MapData.model_validate(data)
        g = build_graph(map_data)

        MAP_STORE[map_data.map_id] = map_data
        GRAPH_STORE[map_data.map_id] = g

        print(f"✅ Map loaded: {map_data.map_id} | nodes={len(map_data.nodes)} edges={len(map_data.edges)}")
    except Exception as e:
        print(f"❌ Failed to load map: {e}")


# ===============================
# Server Startup Event (統一入口)
# ===============================
@app.on_event("startup")
def startup_event():
    # 1. 自動建立資料表 (SQLAlchemy)
    try:
        Base.metadata.create_all(bind=engine) 
        print("✅ Database tables created (if not exist).")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

    # 2. 載入預設地圖
    load_map_logic()


# ===============================
# API: Import Map Manually
# ===============================
@app.post("/maps/import")
def import_map(path: str = "data/map.json"):
    # 這裡可以直接重複利用上面的邏輯，或者保留原本的寫法以回傳 Response
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        map_data = MapData.model_validate(data)
        g = build_graph(map_data)

        MAP_STORE[map_data.map_id] = map_data
        GRAPH_STORE[map_data.map_id] = g

        return {
            "ok": True,
            "map_id": map_data.map_id,
            "nodes": len(map_data.nodes),
            "edges": len(map_data.edges),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===============================
# API: Create Order
# ===============================
@app.post("/orders", response_model=CreateOrderResp, tags=["訂單"])
def create_order(req: CreateOrderReq, db: Session = Depends(get_db)): # 👈 加入 db 依賴
    # 1. 檢查地圖是否載入
    if req.map_id not in GRAPH_STORE:
        raise HTTPException(status_code=404, detail="map_id not loaded; call /maps/import first")

    g = GRAPH_STORE[req.map_id]

    # 2. 路徑規劃演算法 (維持原樣)
    try:
        if req.algorithm == "astar":
            route, dist = astar(g, req.from_node, req.to_node)
        else:
            route, dist = dijkstra(g, req.from_node, req.to_node)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    eta = estimate_eta_sec(route, dist)
    order_id = "O" + uuid.uuid4().hex[:8]

    # 3. ✨ 關鍵修改：寫入 PostgreSQL 資料庫 ✨
    # (取代原本的 ORDER_STORE 和 fake_orders_db)
    new_order = OrderDB(
        id=order_id,
        map_id=req.map_id,
        status="CREATED",
        total_distance_cm=dist,
        eta_sec=eta,
        route=route,          # 直接存 List，DB 會自動轉 JSON
        
        # 商業邏輯欄位
        user_email=req.user_email,
        store_name=req.store_name,
        items=req.items or [],
        total_amount=req.total or 0.0
    )

    try:
        db.add(new_order)      # 加入 Session
        db.commit()            # 送出交易 (真正寫入)
        db.refresh(new_order)  # 重新讀取 (確認有拿到預設值如 created_at)
    except Exception as e:
        db.rollback()          # 如果失敗就回滾，避免資料庫卡住
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # 4. 回傳結果
    return CreateOrderResp(
        order_id=order_id,
        map_id=req.map_id,
        route=route,
        total_distance_cm=dist,
        eta_sec=eta,
    )


# ===============================
# API: Get Order
# ===============================
@app.get("/orders/{order_id}", tags=["訂單"])
def get_order(order_id: str, db: Session = Depends(get_db)): # 👈 加入 db 依賴
    # 使用 SQLAlchemy 查詢
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    # 直接回傳 ORM 物件，FastAPI 會自動幫你轉成 JSON
    return order


@app.get("/")
def read_root():
    return {"message": "Autonomous Delivery Robot API is running!"}


# ===============================
# 🛠️ 臨時測試用 API (測試完可刪除)
# ===============================
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.sql_models import OrderDB

@app.post("/test-db-write")
def test_db_write(db: Session = Depends(get_db)):
    # 1. 建立一筆假資料
    test_id = f"TEST_{uuid.uuid4().hex[:4]}"
    new_order = OrderDB(
        id=test_id,
        map_id="test_map",
        status="DB_TESTING",
        total_distance_cm=100.0,
        eta_sec=50.0,
        route=["nodeA", "nodeB"], # 測試 JSON 欄位
        items=[{"name": "cola", "price": 30}] # 測試 JSON 欄位
    )
    
    # 2. 寫入資料庫
    try:
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        return {"status": "success", "order": new_order}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/test-db-read")
def test_db_read(db: Session = Depends(get_db)):
    # 3. 讀取所有測試資料
    orders = db.query(OrderDB).filter(OrderDB.status == "DB_TESTING").all()
    return orders