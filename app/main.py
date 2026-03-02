from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import uuid
import json
from pathlib import Path

# 資料庫相關
from .database import engine, Base, get_db
from .sql_models import OrderDB, StoreDB, ProductDB

# Pydantic Models & Logic
from .models import MapData, CreateOrderReq, CreateOrderResp
from .graph import build_graph, dijkstra, astar
from .services import estimate_eta_sec
from .state import MAP_STORE, GRAPH_STORE

# Router
from .routers import stores, products, auth, users
from .routers.users import get_current_user
from .ws import ws_router

# 匯入寫死的資料用於初始化資料庫
from .routers.stores import STORE_STORE, PRODUCT_STORE

app = FastAPI(title="ESP32 Car Backend")

# --- CORS 設定 ---
raw_origins = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:5173,http://localhost:8000,https://m8he2shxsm.ap-southeast-2.awsapprunner.com"
)
allowed_origins = [origin.strip() for origin in raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 掛載路由 ---
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stores.router)
app.include_router(products.router)
app.include_router(ws_router)

# 載入地圖邏輯
def load_map_logic(path: str = "data/map.json"):
    try:
        print(f"📍 Loading map from: {path}")
        if not Path(path).exists():
            return
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        map_data = MapData.model_validate(data)
        g = build_graph(map_data)
        MAP_STORE[map_data.map_id] = map_data
        GRAPH_STORE[map_data.map_id] = g
        print(f"✅ Map loaded: {map_data.map_id}")
    except Exception as e:
        print(f"❌ Failed to load map: {e}")

# --- Server Startup ---
@app.on_event("startup")
def startup_event():
    # 1. 自動建立資料表
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables verified.")
        
        # 2. 自動將寫死的店家資料匯入雲端 RDS (若為空)
        db = next(get_db())
        if db.query(StoreDB).count() == 0:
            for info in STORE_STORE.values():
                db.add(StoreDB(**info))
            db.commit()
            print("✅ Default stores imported to RDS.")

        if db.query(ProductDB).count() == 0:
            for info in PRODUCT_STORE.values():
                db.add(ProductDB(**info))
            db.commit()
            print("✅ Default products imported to RDS.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

    load_map_logic()

# API: Create Order
@app.post("/orders", response_model=CreateOrderResp, tags=["訂單"])
def create_order(req: CreateOrderReq, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if req.map_id not in GRAPH_STORE:
        raise HTTPException(status_code=404, detail="map_id not loaded")
    g = GRAPH_STORE[req.map_id]
    try:
        if req.algorithm == "astar":
            route, dist = astar(g, req.from_node, req.to_node)
        else:
            route, dist = dijkstra(g, req.from_node, req.to_node)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    eta = estimate_eta_sec(route, dist)
    order_id = "O" + uuid.uuid4().hex[:8]
    new_order = OrderDB(
        id=order_id, map_id=req.map_id, status="CREATED",
        total_distance_cm=dist, eta_sec=eta, route=route,
        user_email=current_user.email, store_name=req.store_name,
        items=req.items or [], total_amount=req.total or 0.0
    )
    try:
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return CreateOrderResp(order_id=order_id, map_id=req.map_id, route=route, total_distance_cm=dist, eta_sec=eta)

@app.get("/orders/{order_id}", tags=["訂單"])
def get_order(order_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    if order.user_email != current_user.email: raise HTTPException(status_code=403, detail="Forbidden")
    return order

@app.get("/")
def read_root():
    return {"message": "Autonomous Delivery Robot API is running!"}
