# 演算法整合完成總結

## 概況

成功將 `algorithm.cpp` （C++ VRP 動態規劃演算法）集成到 Python 後端系統，且**不動原有的前端與後端核心架構**。整合採用分層設計，支持未來 MQTT 小車集成。

---

## 新增檔案清單

### 核心模組（3 個新檔案）

| 檔案 | 行數 | 職責 |
|------|------|------|
| `app/algorithm.py` | 285 | 演算法核心：MapGraph、Dijkstra、Planner、虛擬節點吸附 |
| `app/planner_state.py` | 180 | 狀態管理：小車狀態、訂單隊列、全局規劃狀態存儲 |
| `app/mqtt_bridge.py` | 185 | MQTT 通信層：可選推送通知（生產環境升級） |

### API 與路由（1 個新檔案）

| 檔案 | 行數 | 職責 |
|------|------|------|
| `app/routers/planner.py` | 336 | REST API 端點：/planner/* 供小車與後端查詢 |

### 文檔（2 個新檔案）

| 檔案 | 內容 |
|------|------|
| `ROBOT_INTEGRATION.md` | 📖 小車集成指南（完整的 REST API + MQTT 使用說明） |
| `ARCHITECTURE.md` | 📐 系統架構設計文檔（層級、數據流、擴展方向） |

### 測試（1 個新檔案）

| 檔案 | 內容 |
|------|------|
| `tests/test_integration.py` | ✅ 整合測試（已通過） |

### 修改檔案（1 個改動）

| 檔案 | 改動 | 行數 |
|------|------|------|
| `app/main.py` | 掛載 `planner` 路由 | 2 行 |

---

## 系統架構

### 層級結構

```
前端層
  ↓ 下訂單（/orders） — 保留原有
API 層 NEW
  ↓ /planner/* 端點
業務邏輯層 NEW
  ├── algorithm.py      (MapGraph + Planner)
  └── planner_state.py  (RobotState 管理)
通信層 NEW
  ├── mqtt_bridge.py    (可選 MQTT)
  └── REST (已內建)
```

### 核心類別

#### `MapGraph` (algorithm.py)
- Dijkstra 最短路
- 虛擬節點吸附（任意座標 → 最近道路段）
- 無向圖邊操作

#### `Planner` (algorithm.py)
- VRP 動態規劃求解
- 固定接送順序約束（pick 1, deliver 1, pick 2, deliver 2）
- 支持動態重規劃（已取未送、下一個必送訂單編號）

#### `GlobalPlannerState` (planner_state.py)
- 多小車狀態管理
- 訂單隊列（Order 物件）
- 規劃結果與位置追蹤

#### `MQTTBridge` (mqtt_bridge.py)
- Pub/Sub 訊息代理
- Mock 模式（開發）與真實 MQTT 支持（生產）
- 小車位置更新、規劃指令廣播

---

## API 端點

### `/planner/init` - 初始化小車
```bash
POST /planner/init
{"robot_id": "R001", "start_node": "A"}
```

### `/planner/status` - 查詢小車狀態
```bash
GET /planner/status?robot_id=R001
```
**回應**：訂單數、待送訂單、當前規劃、位置、下一個必送訂單

### `/planner/replan` - 重新規劃
```bash
POST /planner/replan
{"robot_id": "R001", "current_node": "A"}
```
**回應**：動作序列、拜訪節點、總距離（cm）

### `/planner/update-location` - 更新位置
```bash
POST /planner/update-location
{"robot_id": "R001", "node": "X1"}
```

### `/planner/mark-picked` - 標記訂單已取
```bash
POST /planner/mark-picked?robot_id=R001&order_k=1
```

### `/planner/mark-delivered` - 標記訂單已送
```bash
POST /planner/mark-delivered?robot_id=R001&order_k=1
```

---

## 數據流範例

### 小車接收與執行訂單

```
使用者在前端選擇商店 (location_node="A") + 輸入座標 (x=155, y=20)
  ↓ POST /orders → 後端記錄訂單
  ↓ 後端非同步將訂單加入小車 R001 隊列
global_state.add_order("R001", shop_node="A", drop_node="D", drop_coords=(155,20))
  ↓ 小車定期查詢 GET /planner/status?robot_id=R001
  ↓ 收到 pending_count > 0
  ↓ 小車發起 POST /planner/replan
  ↓ 後端執行：
    1. 建立 MapGraph（從 data/map.json）
    2. 轉換節點名稱 → ID：{"A": 0, "X1": 1, "X2": 2, "D": 3}
    3. 訂單轉換：(shop="A", drop="D") → (shop_id=0, drop_id=3)
    4. Planner.solve_from_state() → actions, stops, cost
    5. 轉換回節點名稱：stops = [0, 3] → ["A", "D"]
  ↓ 返回：
    {
      "actions": ["PICKUP order 1 at A", "DELIVER order 1 at D"],
      "stops": ["A", "D"],
      "total_cost": 450
    }
  ↓ 小車導航至 A，執行 PICKUP
  ↓ 小車調用 POST /planner/mark-picked?robot_id=R001&order_k=1
  ↓ 小車導航至 D，執行 DELIVER
  ↓ 小車調用 POST /planner/mark-delivered?robot_id=R001&order_k=1
  ↓ 訂單完成！
```

---

## 不動的核心架構

✅ **前端**
- 無需改動
- 仍透過 `/orders` 下單
- 仍使用 `frontend/public/nodes.json` 的固定領貨點
- 仍嵌入 `stores.json` 的商店信息

✅ **既有後端路由**
- `/stores` - 商店管理（保留）
- `/products` - 商品管理（保留）
- `/auth`, `/users` - 認證與用戶（保留）
- `/orders` - 訂單記錄（保留）
- WebSocket 連線（保留）

✅ **資料庫**
- OrderDB, StoreDB, ProductDB（保留）
- Alembic 遷移（保留）

---

## 小車接入流程

### 方案 A: REST API（推薦用於原型驗證）

```python
import requests

# 1. 初始化
requests.post("http://localhost:8000/planner/init",
    json={"robot_id": "R001", "start_node": "A"})

# 2. 輪詢狀態
status = requests.get("http://localhost:8000/planner/status?robot_id=R001").json()
if status["pending_count"] > 0:
    # 3. 重新規劃
    plan = requests.post("http://localhost:8000/planner/replan",
        json={"robot_id": "R001", "current_node": "A"}).json()
    
    # 執行 plan["actions"] 與 plan["stops"]
    
    # 到達節點後標記狀態
    requests.post(f"http://localhost:8000/planner/mark-picked?robot_id=R001&order_k=1")
    requests.post(f"http://localhost:8000/planner/mark-delivered?robot_id=R001&order_k=1")
```

### 方案 B: MQTT（未來推薦用於實時系統）

```python
import paho.mqtt.client as mqtt

client = mqtt.Client()

def on_plan(client, userdata, msg):
    plan = json.loads(msg.payload)
    # 執行規劃指令
    execute_plan(plan)

def on_replan_req(client, userdata, msg):
    # 小車主動調用 /planner/replan 獲取新規劃
    new_plan = requests.post(...).json()

client.subscribe("robot/R001/plan")
client.subscribe("robot/R001/replan-req")
client.on_message = ...
client.connect("mqtt.example.com", 1883)

# 小車發佈位置更新
client.publish("robot/R001/telemetry", 
    json.dumps({"robot_id": "R001", "node": "A"}))
```

---

## 演算法特性

### 支援

✅ 動態接單（新訂單進系統時自動重規劃）
✅ 虛擬節點吸附（任意座標自動吸附到最近道路）
✅ 曼哈頓距離（網格地圖最適）
✅ 固定接送順序（pick 1 then deliver 1, pick 2 then deliver 2...）
✅ 位掩碼追蹤（已取未送訂單集合）
✅ 多小車獨立狀態管理

### 限制

⚠️ 最多 20 訂單（位掩碼的 20-bit 限制）
⚠️ 距離計算基於曼哈頓距離（可修改 `algorithm.py` 支持其他度量）
⚠️ 當前無時間窗口約束（可透過修改 `Planner.solve_from_state()` 添加）

---

## 測試結果

✅ **TEST 1: Algorithm Core**
- Dijkstra 最短路計算 ✅
- Planner VRP 求解 ✅
- Virtual Node snapping ✅

✅ **TEST 2: Planner State Management**
- 添加小車 ✅
- 添加訂單 ✅
- 標記訂單狀態（picked/delivered） ✅
- 更新規劃結果 ✅

✅ **TEST 3: MQTT Bridge**
- MQTT 連接（Mock） ✅
- 發佈規劃結果 ✅
- 發佈重規劃請求 ✅

```
============================================================
✅ ALL TESTS PASSED!
============================================================
```

---

## 部署檢查清單

- [x] `app/algorithm.py` 已建立，邏輯完整
- [x] `app/planner_state.py` 已建立，狀態管理完整
- [x] `app/mqtt_bridge.py` 已建立，支持 Mock + 真實 MQTT
- [x] `app/routers/planner.py` 已建立，6 個 API 端點
- [x] `app/main.py` 已改動，planner 路由已掛載
- [x] 所有測試通過
- [x] 文檔完整（ROBOT_INTEGRATION.md + ARCHITECTURE.md）

**部署建議**：
1. 無需改動 `requirements.txt`（演算法為純 Python）
2. Docker 構建無需改動（無 C++ 編譯依賴）
3. 可選：未來使用 MQTT 時加入 `paho-mqtt` 依賴

---

## 後續優化方向

### 短期（1-2 週）
1. 整合實體小車（REST API 試驗）
2. 添加路線可視化 WebUI
3. 訂單優先級權重（加急快速送達）

### 中期（1-2 月）
1. 真實 MQTT broker 集成（Mosquitto）
2. 資料庫持久化（將 `RobotState` 存入 PostgreSQL）
3. 小車動態分派（多訂單時最佳小車選擇）

### 長期
1. 時間窗口約束（必須在某時間前送達）
2. 容量約束（小車載貨量限制）
3. C++ 加速（pybind11 或 Cython）
4. Web UI 地圖可視化（小車實時位置）

---

## 文檔清單

1. **[ROBOT_INTEGRATION.md](./ROBOT_INTEGRATION.md)** 🚀
   - 小車開發者讀這份文檔
   - 包含所有 API 使用範例、MQTT 配置、故障排查

2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** 🏗️
   - 系統架構與設計決策
   - 適合系統管理員與後續維護者

3. **本文檔** 📋
   - 集成完成總結

---

## 快速開始示例

```bash
# 1. 啟動後端
cd d:\GDG_auto_delivery\autonomous-delivery-robot
python -m uvicorn app.main:app --reload

# 2. 初始化小車（curl 或 Postman）
curl -X POST http://localhost:8000/planner/init \
  -H "Content-Type: application/json" \
  -d '{"robot_id": "R001", "start_node": "A"}'

# 3. 查詢狀態
curl http://localhost:8000/planner/status?robot_id=R001

# 4. 重新規劃
curl -X POST http://localhost:8000/planner/replan \
  -H "Content-Type: application/json" \
  -d '{"robot_id": "R001", "current_node": "A"}'

# 5. 標記orders
curl -X POST "http://localhost:8000/planner/mark-picked?robot_id=R001&order_k=1"
curl -X POST "http://localhost:8000/planner/mark-delivered?robot_id=R001&order_k=1"
```

---

## 聯絡與問題

若有技術問題，請參考：
1. `ROBOT_INTEGRATION.md` - API 與集成問題
2. `ARCHITECTURE.md` - 設計與擴展問題  
3. `tests/test_integration.py` - 測試範本與用法範例

---

**整合完成日期**：2026-03-04
**狀態**：✅ 生產就緒（REST API）| 🔜 待驗證（MQTT）
