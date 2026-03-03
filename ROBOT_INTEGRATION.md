# 小車整合指南

本文檔說明如何將實體小車整合到自動配送機器人系統中，並透過演算法獲取最優路徑。

## 系統架構概覽

```
前端 (React)
  ↓ 下訂單（選擇商店 + 輸入收貨點）
後端 API (/orders)
  ↓ 記錄訂單到資料庫
全局規劃狀態 (app/planner_state.py)
  ↓ 存放待執行訂單、小車狀態
規劃引擎 (app/algorithm.py)
  ↓ 執行 Dijkstra + VRP 求解
API 端點 (/planner/replan)
  ↓ 回傳最優路徑與動作序列
小車 (MQTT 或 REST)
  ↓ 執行規劃指令、發送位置更新
MQTT 橋接 (app/mqtt_bridge.py)
  ↓ 雙向通信、狀態同步
```

**核心原則**：
- ✅ 不動前端與既有的 `/orders` API
- ✅ 規劃層在後端服務層中隔離（`app/algorithm.py` + `app/planner_state.py`）
- ✅ 小車透過新的 `/planner` 端點或 MQTT 與後端通信

---

## 快速開始：小車 REST API 集成

### 1. 初始化小車

小車啟動時，須向後端註冊自己：

```bash
curl -X POST http://localhost:8000/planner/init \
  -H "Content-Type: application/json" \
  -d '{"robot_id": "R001", "start_node": "A"}'
```

**回應**：
```json
{
  "robot_id": "R001",
  "start_node": "A",
  "message": "Robot initialized"
}
```

**說明**：
- `robot_id`: 小車唯一識別碼（自訂，例如 "R001", "R002"）
- `start_node`: 初始位置（使用系統中固定的節點名稱，見 `frontend/public/nodes.json`）
  - 預設值：`"A"`（大門口）
  - 其他選項：`"X1"`, `"X2"`, `"D"` 等

### 2. 接收訂單（由後端推動，或小車主動查詢）

後端接收到新訂單後，自動將其加入小車的待執行隊列。小車可定期查詢目前狀態：

```bash
curl http://localhost:8000/planner/status?robot_id=R001
```

**回應**：
```json
{
  "robot_id": "R001",
  "current_node": "A",
  "next_deliver_k": 1,
  "picked_mask": 0,
  "orders_count": 3,
  "pending_count": 3,
  "last_plan_cost": 1250,
  "plan_actions": [
    "PICKUP order 1 at shop node A",
    "DELIVER order 1 at drop node X1",
    "PICKUP order 2 at shop node X1",
    "DELIVER order 2 at drop node D",
    ...
  ],
  "plan_stops": ["A", "X1", "X1", "D", ...]
}
```

**欄位說明**：
- `current_node`: 小車當前位置（節點名稱）
- `next_deliver_k`: 下一個必須送的訂單編號（1-indexed）
- `picked_mask`: 位掩碼，表示已取但未送的訂單（二進制表示）
  - 例如 `picked_mask=0b0101` 表示訂單 1 和 3 已取，訂單 2 未取
- `orders_count`: 總訂單數
- `pending_count`: 待執行訂單數（包括已取 + 未取）
- `last_plan_cost`: 上次規劃的總距離（cm）
- `plan_actions`: 動作序列（PICKUP / DELIVER）
- `plan_stops`: 拜訪節點序列

### 3. 執行規劃

當小車要重新規劃路徑時（例如接收新訂單後），發送 replan 請求：

```bash
curl -X POST http://localhost:8000/planner/replan \
  -H "Content-Type: application/json" \
  -d '{"robot_id": "R001", "current_node": "A"}'
```

**回應**：
```json
{
  "robot_id": "R001",
  "success": true,
  "total_cost": 1500,
  "actions": [
    "PICKUP order 1 at shop node A",
    "DELIVER order 1 at drop node X1",
    ...
  ],
  "stops": ["A", "X1", "D", ...],
  "timestamp": "2026-03-04T10:30:00"
}
```

**說明**：
- 若 `success=false`，表示當前無待執行訂單或規劃失敗
- `actions`: 依序執行的動作
- `stops`: 拜訪節點的順序（小車可用此導航）
- `total_cost`: 總距離（單位：cm，基於曼哈頓距離）

### 4. 更新小車位置與訂單狀態

當小車到達一個節點並完成動作時，須更新後端狀態：

```bash
# 更新當前位置
curl -X POST http://localhost:8000/planner/update-location \
  -H "Content-Type: application/json" \
  -d '{"robot_id": "R001", "node": "X1"}'

# 標記訂單已取
curl -X POST "http://localhost:8000/planner/mark-picked?robot_id=R001&order_k=1"

# 標記訂單已送
curl -X POST "http://localhost:8000/planner/mark-delivered?robot_id=R001&order_k=1"
```

**流程示例**：
1. 小車在節點 "A" 接收到訂單編號 1（`order_k=1`）
2. 小車移動到商店（仍在 "A"），執行 PICKUP 動作
3. 調用 `/mark-picked?robot_id=R001&order_k=1`
4. 微車根據 `plan_stops` 移動至 "X1"（送達點）
5. 調用 `/update-location` 更新位置為 "X1"
6. 執行 DELIVER 動作
7. 調用 `/mark-delivered?robot_id=R001&order_k=1`
8. 系統自動重新規劃下一筆訂單

---

## MQTT 集成（進階，可選）

若小車搭載 MQTT 客戶端，可透過 MQTT 進行無狀態化通信。

### MQTT 主題結構

```
robot/{robot_id}/telemetry      ← 小車發佈：位置、狀態
robot/{robot_id}/plan           ← 後端發佈：規劃結果
robot/{robot_id}/replan-req     ← 後端發佈：重新規劃請求
```

### 小車發佈（Telemetry）

小車定期發佈位置與狀態：

**主題**：`robot/R001/telemetry`

**Payload**：
```json
{
  "robot_id": "R001",
  "node": "A",
  "timestamp": "2026-03-04T10:30:00"
}
```

### 後端發佈（Plan）

後端在規劃完成後，發佈規劃結果：

**主題**：`robot/R001/plan`

**Payload**：
```json
{
  "robot_id": "R001",
  "actions": [
    "PICKUP order 1 at shop node A",
    "DELIVER order 1 at drop node X1"
  ],
  "stops": ["A", "X1"],
  "timestamp": "2026-03-04T10:30:00"
}
```

### 後端發佈（Replan Request）

當有新訂單時，後端可主動要求小車重新規劃：

**主題**：`robot/R001/replan-req`

**Payload**：
```json
{
  "robot_id": "R001",
  "request_time": "2026-03-04T10:30:00"
}
```

**小車應響應**：在收到 replan-req 後，小車調用 `/planner/replan` 端點獲取新規劃。

### 啟用 MQTT（開發環境）

在後端啟動時，已默認使用 Mock MQTT 客戶端（無需真實 broker）。

若要使用真實 MQTT broker（例如 Mosquitto），修改 `app/main.py`：

```python
from .mqtt_bridge import get_mqtt_bridge

@app.on_event("startup")
async def startup_mqtt():
    # 註冊 MQTT 橋接
    mqtt = get_mqtt_bridge(broker_url="mqtt://localhost:1883", use_mock=False)
    if mqtt.start():
        print("✅ MQTT bridge started")
    else:
        print("❌ MQTT connection failed")

@app.on_event("shutdown")
async def shutdown_mqtt():
    mqtt = get_mqtt_bridge()
    mqtt.stop()
```

---

## 節點與商店的對應關係

系統使用**固定的節點網路**，由 `frontend/public/nodes.json` 定義：

```json
[
  {"id": "A", "name": "大門口", "x": 0, "y": 0},
  {"id": "X1", "name": "中庭", "x": 50, "y": 0},
  {"id": "X2", "name": "走廊", "x": 100, "y": 0},
  {"id": "D", "name": "圖書館", "x": 150, "y": 0}
]
```

商店繫結至節點（`frontend/public/stores.json`）：

```json
[
  {"id": "S001", "name": "讚野烤肉飯", "location_node": "A", ...},
  {"id": "S002", "name": "台灣第二味", "location_node": "A", ...},
  {"id": "S003", "name": "8-11便利商店", "location_node": "X1", ...}
]
```

**流程**：
1. 使用者在前端選擇商店（例如 S001，位於節點 "A"）
2. 輸入收貨點座標（任意 (x, y)）
3. 後端演算法將座標吸附到最近的道路段，生成虛擬節點
4. 規劃引擎計算從 "A" 到虛擬節點的最優路徑

**固定節點的作用**：
- ✅ 前端預設領貨點（不動）
- ✅ 小車導航基準點
- ✅ 規劃演算法的主要頂點

---

## 動態重規劃（Dynamic Replan）

系統支持**動態接單與重規劃**：

1. 當新訂單進入系統時，自動加入小車的待執行隊列
2. 小車可在運行中隨時調用 `/planner/replan` 獲取更新的最優路徑
3. 規劃考慮當前的 picked_mask（已取未送的訂單）和 next_deliver_k（下一個必送訂單號）
4. 約束：訂單接送順序為**固定的**（先取 1 再送 1，再取 2 再送 2，...）

**範例**：
- 小車已取訂單 1 並在運送中（picked_mask=1, next_deliver_k=2）
- 此時有新訂單 2 進入系統
- 小車調用 `/planner/replan` 獲取最優路徑：可能先送完 1，再去取 2，然後送 2

---

## 小車實裝檢查清單

- [ ] 實現 HTTP 客戶端，支持 POST/GET 請求
- [ ] 啟動時調用 `/planner/init` 初始化自己
- [ ] 定期調用 `/planner/status` 檢查新訂單與當前規劃
- [ ] 根據 `plan_actions` 和 `plan_stops` 執行導航和動作
- [ ] 到達節點時調用 `/update-location`
- [ ] 完成 PICKUP/DELIVER 動作後調用 `/mark-picked` 和 `/mark-delivered`
- [ ] （可選）實現 MQTT 客戶端以支持推送更新
- [ ] 下載 `frontend/public/nodes.json` 至本地，用於座標參考

---

## 演算法限制

- **最多訂單數**：20 筆（演算法的位掩碼限制）
- **距離計算**：曼哈頓距離（基於 $|x_1-x_2| + |y_1-y_2|$）
- **座標單位**：公分（cm）
- **道路吸附**：虛擬節點會自動吸附到最近的線段，無需手動指定

---

## 故障排查

### 503 Map not loaded

**原因**：`data/map.json` 未被正確加載

**解決**：
1. 檢查 `data/map.json` 是否存在
2. 確認 JSON 格式正確
3. 檢查後端啟動日誌中是否有加載成功的消息

### Planner failed

**原因**：演算法無法找到可行解

**排查**：
1. 檢查訂單數是否超過 20 筆
2. 確認節點之間是否連通（圖結構完整）
3. 檢查 `current_node` 是否為有效節點名稱

### 位置更新無效

**原因**：節點名稱不匹配

**排查**：
1. 對照 `frontend/public/nodes.json` 確認節點 ID
2. 確認大小寫正確（通常為單一字母或 "X1", "X2" 等）

---

## 範例：完整訂單流程

```
時刻 0:00   後端接收訂單：shop="A", drop_coords=(55,0)
           後端吸附座標到最近線段，生成虛擬節點 V
           後端將訂單 1 加入小車 R001 的隊列
           小車自動調用 /planner/replan

時刻 0:05   小車 R001 收到規劃結果：
           - PICKUP order 1 at shop node A
           - DELIVER order 1 at drop node V
           小車導航至節點 A

時刻 0:10   小車到達 A，執行 picked 標記
           調用 POST /planner/mark-picked?robot_id=R001&order_k=1

時刻 0:20   小車導航至虛擬節點 V，完成 deliver
           調用 POST /planner/mark-delivered?robot_id=R001&order_k=1

時刻 0:25   訂單完成，小車返回待命狀態
           查詢 /planner/status→pending_count=0
```

---

## 進階：自訂演算法參數

若需要調整演算法行為（例如修改距離計算、添加優先級權重等），修改 `app/algorithm.py` 中的相應函數，無需動到其他模組。

---

祝小車開發順利！ 🚀
