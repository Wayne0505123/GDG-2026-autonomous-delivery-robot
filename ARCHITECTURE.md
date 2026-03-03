# 演算法整合架構設計

## 概覽

本文檔描述將 `algorithm.cpp` 整合到自動配送系統的完整架構，包括目錄結構、數據流、以及與 MQTT 小車系統的無縫銜接。

## 核心原則

✅ **不動前端與既有後端架構**
- 前端仍透過 `/orders` 下單，無需改動
- 後端原有的路由（stores, products, auth, users）保留不變
- 新增層級完全隔離在 `/planner` 端點

✅ **演算法層完全可復用**
- `app/algorithm.py`：純業務邏輯，無與 FastAPI 相關的依賴
- 支持以外掛程式方式嵌入任何 Python 應用

✅ **狀態管理獨立**
- `app/planner_state.py`：運行時狀態存儲，未來可搭配資料庫
- 支持多小車、動態重規劃、狀態持久化

✅ **通信層靈活**
- REST API (`/planner/*`)：同步查詢，適合輪詢
- MQTT 橋接 (`app/mqtt_bridge.py`)：非同步推送，適合實時性要求高的場景
- 兩套系統獨立，小車可選任一或混合使用

---

## 檔案層級結構

```
app/
├── algorithm.py              ⭐ 核心演算法層
│   ├── Edge
│   ├── MapGraph (地圖 + Dijkstra)
│   ├── Planner (VRP 動態規劃)
│   └── 輔助函數（狀態打包、座標吸附）
│
├── planner_state.py          ⭐ 狀態管理層
│   ├── Order
│   ├── RobotState
│   └── GlobalPlannerState (全局狀態)
│
├── mqtt_bridge.py            ⭐ MQTT 通信層（可選）
│   ├── MockMQTTClient
│   └── MQTTBridge
│
├── routers/
│   ├── planner.py            ⭐ API 層（REST 端點）
│   │   ├── POST /planner/init
│   │   ├── GET  /planner/status
│   │   ├── POST /planner/replan
│   │   ├── POST /planner/update-location
│   │   ├── POST /planner/mark-picked
│   │   └── POST /planner/mark-delivered
│   │
│   ├── stores.py             (原有，保留)
│   ├── products.py           (原有，保留)
│   ├── auth.py               (原有，保留)
│   └── users.py              (原有，保留)
│
├── main.py                   (改動：掛載 planner 路由)
├── graph.py                  (原有，保留)
├── models.py                 (原有，保留)
├── services.py               (原有，保留)
├── database.py               (原有，保留)
├── sql_models.py             (原有，保留)
├── state.py                  (原有，保留)
└── ws.py                     (原有，保留)

data/
└── map.json                  (原有：固定地圖結構)

frontend/
└── public/
    ├── nodes.json            (原有：固定節點定義)
    └── stores.json           (原有：商店 + location_node 關聯)

ROBOT_INTEGRATION.md          ⭐ 小車集成指南（新增）
ARCHITECTURE.md               ⭐ 本文檔（新增）
```

---

## 數據流

### 1. 前端下訂單（不動）

```
前端 (React)
  ↓ POST /orders
    {
      "map_id": "campus_demo",
      "from_node": "A",       // 商店位置（固定）
      "to_node": "D",         // 收貨點（前端可選任意節點）
      "store_name": "讚野烤肉飯",
      "items": ["招牌便當 x1"]
    }
  ↓ 後端 /orders 端點
  後端資料庫
    → 記錄到 OrderDB
    → 計算最短路徑
    → 返回 route, distance, eta
```

**特點**：此流程**完全不動**，與新演算法無關。

### 2. 後端接收訂單 → 通知小車（新增）

```
後端資料庫新增訂單
  ↓ （可選）非同步腳本或 WebSocket 監聽
  ↓ 主動將訂單加入小車隊列
    state.add_order("R001", shop_node="A", drop_node="drop_virtual_node_123")
  ↓ 發送 MQTT 或 REST 通知小車
    "有新訂單，請重新規劃"
  ↓
小車收到通知
  ↓ GET /planner/status (查詢當前狀況)
  ↓ POST /planner/replan (發起規劃)
    {
      "robot_id": "R001",
      "current_node": "A"
    }
```

### 3. 規劃引擎執行（新增）

```
/planner/replan 端點
  ↓ 取得小車狀態 (current_node, next_deliver_k, picked_mask)
  ↓ 取得待執行訂單 (order_1, order_2, ...)
  ↓ 建立 MapGraph 結構 (from data/map.json)
  ↓ 轉換訂單節點名稱 → 節點 ID (node_mapping)
  ↓ 建立 Planner 物件
  ↓ 執行 planner.solve_from_state()
    → Dijkstra 多源最短路徑
    → DP 求解 VRP
  ↓ 返回 (actions, stops, cost)
  ↓ 存儲至 robot_state.plan_actions / plan_stops
  ↓ 返回 HTTP 200 + 規劃結果
```

### 4. 小車執行規劃（新增）

```
小車收到規劃結果
  ↓ 解析 plan_stops: ["A", "X1", "D", ...]
  ↓ 遵循 plan_actions: ["PICKUP order 1 at A", "DELIVER order 1 at D", ...]
  ↓ 導航至各節點
  ↓ 完成動作後，標記訂單狀態
    POST /planner/mark-picked?robot_id=R001&order_k=1
    POST /planner/mark-delivered?robot_id=R001&order_k=1
  ↓ 更新位置
    POST /planner/update-location
      {"robot_id": "R001", "node": "X1"}
  ↓ 查詢新規劃
    GET /planner/status
    POST /planner/replan (若有新訂單)
```

---

## 對象設計

### 1. `MapGraph`（演算法層）

**職責**：
- 存儲地圖節點與邊
- 運行 Dijkstra 計算最短路
- 支持虛擬節點吸附（snap to road）

**介面**：
```python
mp = MapGraph()
mp.add_node(x, y)  # 返回節點 ID
mp.add_undirected_edge(u, v, weight)
mp.dijkstra(src)  # 返回從 src 到所有節點的距離
mp.add_virtual_node_snapped_to_road(x, y)  # 任意座標 → 虛擬節點
```

**與 API 層的銜接**：
```python
# 在 /planner/replan 中使用
mp = build_algorithm_graph()  # 從 data/map.json 構建
node_mapping = get_node_id_mapping()  # 節點名稱 ↔ ID 轉換
algo_orders = [(node_mapping[shop], node_mapping[drop]) 
               for shop, drop in orders]
```

### 2. `Planner`（演算法層）

**職責**：
- VRP 問題求解
- 支持動態接單與重規劃
- 固定接送順序約束

**介面**：
```python
planner = Planner(mp, start_node_id, orders_list)
  # orders_list: [(shop_id, drop_id), ...]
ok, actions, stops, cost = planner.solve_from_state(
  next_deliver_k=1,  # 下一個必須送的訂單號
  picked_mask=0      # 已取未送的掩碼（位表示）
)
# 返回: (可行性, 動作列表, 拜訪節點, 總成本)
```

### 3. `RobotState`（狀態管理層）

**職責**：
- 存儲單台小車的狀態
- 管理訂單清單
- 記錄規劃結果

**介面**：
```python
state = RobotState(robot_id="R001", current_node="A")
state.all_orders[k] = Order(...)  # 訂單編號 k
state.picked_mask = 0b0011  # 示例：訂單 1,2 已取
state.next_deliver_k = 1  # 下一個必送的訂單
state.plan_actions = [...]  # 最新規劃結果
state.plan_stops = [...]
```

### 4. `GlobalPlannerState`（狀態管理層）

**職責**：
- 全局狀態存儲
- 支持多小車

**介面**：
```python
global_state = get_global_state()
global_state.add_robot("R001", start_node="A")
global_state.add_order("R001", shop_node="A", drop_node="D")
global_state.update_plan("R001", actions, stops, cost)
global_state.mark_order_picked("R001", k=1)
global_state.mark_order_delivered("R001", k=1)
```

### 5. `MQTTBridge`（通信層，可選）

**職責**：
- MQTT Pub/Sub 代理
- 小車與後端的即時通信

**介面**：
```python
mqtt = get_mqtt_bridge()
mqtt.start()
mqtt.publish_plan("R001", actions, stops)
mqtt.publish_replan_request("R001")
mqtt.register_telemetry_callback("R001", on_telemetry_cb)
```

---

## 核心流程示例

### 情景：使用者下訂，小車收到並重規劃

```python
# ============ 步驟 1: 前端下訂單 ============
# 前端傳送：{"map_id": "campus_demo", "from_node": "A", "to_node": "D"}
# 後端 /orders 端點處理，返回最短路

POST /orders
  → 記錄到資料庫
  → 計算 route(A→...→D), distance, eta
  → 返回給前端


# ============ 步驟 2: 後端將訂單加入小車隊列（新增） ============
# 後端異步或主動將訂單加入小車 R001 的待執行隊列
from app.planner_state import get_global_state

global_state = get_global_state()
order_id = global_state.add_order(
    robot_id="R001",
    shop_node="A",        # 商店節點
    drop_node="drop_vnode_1",  # 可能是虛擬節點
    drop_coords=(165, 20)  # 原始座標（若使用 snap）
)


# ============ 步驟 3: 小車查詢狀態 ============
GET /planner/status?robot_id=R001
  → 返回 pending_orders, plan_actions, plan_stops


# ============ 步驟 4: 小車發起重規劃 ============
POST /planner/replan
  {
    "robot_id": "R001",
    "current_node": "A"  # 小車當前位置
  }


# ============ 步驟 5: 後端規劃引擎執行 ============
# /planner/replan 端點內部處理：

# 5.1 取得小車狀態
robot = state.get_robot("R001")
# 現在：current_node="A", next_deliver_k=1, picked_mask=0

# 5.2 建立演算法圖
mp = build_algorithm_graph()  # 從 data/map.json
node_mapping = {"A": 0, "X1": 1, "X2": 2, "D": 3}

# 5.3 訂單轉換
orders_list = robot.get_pending_orders()  # [(1, Order)]
algo_orders = [(node_mapping["A"], node_mapping["drop_vnode_1"])]
  # = [(0, 4)]  (假設虛擬節點 ID=4)

# 5.4 規劃求解
planner = Planner(mp, start_id=0, orders=algo_orders)
ok, actions, stops, cost = planner.solve_from_state(
    next_deliver_k=1,
    picked_mask=0
)
# 返回：
#   ok = True
#   actions = ["PICKUP order 1 at A", "DELIVER order 1 at drop_vnode_1"]
#   stops = [0, 4]
#   cost = 165  (cm)

# 5.5 轉換回節點名稱
reverse_mapping = {v: k for k, v in node_mapping.items()}
stops_names = [reverse_mapping[s] for s in stops]
  # = ["A", "drop_vnode_1"]

# 5.6 保存規劃結果
state.update_plan("R001", actions, stops_names, cost)

# 5.7 返回 HTTP 回應
return ReplanResponse(
    robot_id="R001",
    success=True,
    total_cost=165,
    actions=actions,
    stops=stops_names
)


# ============ 步驟 6: 小車執行規劃 ============
# 小車收到 plan_stops = ["A", "drop_vnode_1"]
# 解析 plan_actions[0] = "PICKUP order 1 at A"
# 導航至 A，執行取貨動作

POST /planner/mark-picked?robot_id=R001&order_k=1
  → 更新 picked_mask = 0b01 (第 1 位=1)
  → Order.status = "picked"

# 導航至 drop_vnode_1

POST /planner/mark-delivered?robot_id=R001&order_k=1
  → 更新 picked_mask = 0b00 (第 1 位=0)
  → Order.status = "delivered"
  → next_deliver_k = 2

# ============ 步驟 7: 循環 ============
# 小車再次查詢 status 或監聽 MQTT
# 若有新訂單，重複步驟 2→7
```

---

## 與前端領貨點的整合

### 前端的固定領貨點

**nodes.json** 中定義了 4 個固定節點：
```json
[
  {"id": "A", "name": "大門口"},
  {"id": "X1", "name": "中庭"},
  {"id": "X2", "name": "走廊"},
  {"id": "D", "name": "圖書館"}
]
```

### 商店與節點的綁定

**stores.json** 中，每個商店有 `location_node`：
```json
[
  {"id": "S001", "name": "讚野烤肉飯", "location_node": "A"},
  {"id": "S003", "name": "8-11便利商店", "location_node": "X1"}
]
```

### 收貨點的靈活性

**當使用者在前端選擇商店 + 輸入收貨點座標時**：
1. 前端向後端發送 `/orders` 請求（現有流程）
2. 後端計算從商店→收貨點的最短路
3. **新增流程**：當小車被指派此訂單時，演算法層使用虛擬節點吸附
   - 若收貨點座標 (x, y) 不是固定節點，自動吸附到最近的道路段
   - 生成虛擬節點，計算到該虛擬節點的路徑
4. 小車導航至虛擬節點完成送貨

**結論**：
- ✅ 前端的領貨點選單（nodes.json）完全不動
- ✅ 任意座標收貨點透過虛擬節點吸附無縫支持
- ✅ 商店綁定（location_node）作為規劃的起點

---

## 多小車與狀態持久化

### 當前設計（單小車，記憶體狀態）

```python
global_state = GlobalPlannerState()  # 全局單例

global_state.add_robot("R001", start_node="A")
global_state.add_robot("R002", start_node="D")

# 每個小車有獨立的狀態
state_r001 = global_state.get_robot("R001")
state_r002 = global_state.get_robot("R002")
```

### 未來升級（多小車 + 資料庫持久化）

```python
# app/planner_state.py 可擴展為：
# 1. 將 RobotState 持久化到資料庫表
# 2. 實現樂觀鎖機制確保並發安全
# 3. 支持狀態快照和回放

from sqlalchemy import Column, Integer, String
from .database import Base

class RobotStateDB(Base):
    __tablename__ = "robot_states"
    
    robot_id = Column(String, primary_key=True)
    current_node = Column(String)
    next_deliver_k = Column(Integer)
    picked_mask = Column(Integer)
    plan_actions = Column(JSON)
    plan_stops = Column(JSON)
    last_replan_time = Column(DateTime)
```

---

## 測試

### 單元測試範本

```python
# tests/test_algorithm.py
from app.algorithm import MapGraph, Planner

def test_dijkstra():
    mp = MapGraph()
    n0 = mp.add_node(0, 0)
    n1 = mp.add_node(100, 0)
    n2 = mp.add_node(100, 100)
    
    mp.add_undirected_edge(n0, n1, 100)
    mp.add_undirected_edge(n1, n2, 100)
    
    dist = mp.dijkstra(n0)
    assert dist[n1] == 100
    assert dist[n2] == 200

def test_planner():
    # ... 建立圖 ...
    planner = Planner(mp, start_id=0, orders=[(1, 2), (3, 4)])
    ok, actions, stops, cost = planner.solve_from_state(1, 0)
    assert ok == True
    assert len(actions) > 0
```

### 集成測試

```bash
# 1. 啟動後端
python -m uvicorn app.main:app --reload

# 2. 初始化小車
curl -X POST http://localhost:8000/planner/init \
  -H "Content-Type: application/json" \
  -d '{"robot_id": "R001", "start_node": "A"}'

# 3. 添加訂單（模擬）
# 使用 Python 腳本直接調用 global_state

# 4. 執行重規劃
curl -X POST http://localhost:8000/planner/replan \
  -H "Content-Type: application/json" \
  -d '{"robot_id": "R001", "current_node": "A"}'

# 5. 檢驗結果
curl http://localhost:8000/planner/status?robot_id=R001
```

---

## 性能考量

| 指標 | 預期值 | 備註 |
|------|--------|------|
| Dijkstra (4 節點) | <1ms | 預計算所有重要點距離 |
| Planner (3 訂單) | 10ms | DP 狀態數：O(2^n × n × k_max) |
| API 端點 (replan) | 50-100ms | 包括圖構建、轉換隔層、DP求解 |
| MQTT 推送延遲 | <500ms | 依賴 broker 配置 |

---

## 部署

### Docker

Dockerfile 無需改動（無新 C++ 依賴）：
```dockerfile
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 環境變數

（可選）增加 MQTT broker 設置：
```bash
MQTT_BROKER_URL=mqtt://localhost:1883
MQTT_USE_MOCK=true  # 開發時使用 Mock，生產切換為 false
```

---

## 後續優化方向

1. **性能**
   - 預計算距離矩陣緩存
   - 使用 C 擴展加速 Dijkstra（pybind11 或 Cython）

2. **功能**
   - 優先級訂單
   - 時間window 約束（訂單必須在某時間內送達）
   - 多車協作（訂單分派算法）

3. **運維**
   - 規劃結果日誌與分析
   - 異常檢測（無法送達的訂單）
   - Web UI 顯示小車即時位置與規劃路徑

---

## 相關文件

- [ROBOT_INTEGRATION.md](./ROBOT_INTEGRATION.md) - 小車集成指南（REST API + MQTT）
- [app/algorithm.py](./app/algorithm.py) - 演算法核心實現
- [app/planner_state.py](./app/planner_state.py) - 狀態管理
- [app/routers/planner.py](./app/routers/planner.py) - API 層

---

**最後更新**：2026-03-04
