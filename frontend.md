# 前端購物平台與即時地圖顯示

> 模組二 | 更新日期：2026/01/09

---

## 我的職責範圍

根據分工文件，我負責(廖紀翔)：

- [x] 使用者購物平台介面設計
- [ ] 商品列表、商品詳細頁
- [ ] 購物車與訂單建立流程
- [ ] 訂單狀態顯示（未出貨／配送中／完成）
- [ ] 即時配送地圖介面設計
- [ ] 車輛位置即時更新與視覺化
- [ ] 配送完成通知顯示
- [ ] 前端操作流程與使用者體驗設計

---

## 技術選型

| 類別 | 選擇 | 理由 |
|------|------|------|
| 框架 | **Vite + React** | 開發快、HMR、SPA 適合即時更新 |
| 樣式 | **Tailwind CSS** | 快速刻版、RWD 內建 |
| 地圖 | **Canvas 自繪** | 室內固定路網，不需 Google Maps |
| 狀態 | **Zustand** | 輕量、比 Redux 簡單 |
| 部署 | **Nginx on Linux** | 靜態檔 + 反向代理後端 |

---

## 專案結構

```
frontend/
├── public/
│   └── map.json              # 地圖資料（從後端拿或複製一份）
├── src/
│   ├── components/
│   │   ├── Navbar.jsx
│   │   ├── ProductCard.jsx   # 商品卡片
│   │   ├── CartDrawer.jsx    # 購物車側邊欄
│   │   ├── OrderStatus.jsx   # 訂單狀態 badge
│   │   ├── LiveMap.jsx       # 即時地圖（核心）
│   │   └── RobotMarker.jsx   # 小車標記
│   ├── pages/
│   │   ├── Home.jsx          # 商品列表
│   │   ├── Product.jsx       # 商品詳細
│   │   ├── Cart.jsx          # 購物車
│   │   ├── Checkout.jsx      # 結帳
│   │   └── Tracking.jsx      # 訂單追蹤 + 地圖
│   ├── hooks/
│   │   ├── useWebSocket.js   # WS 連線
│   │   └── useCart.js        # 購物車邏輯
│   ├── stores/
│   │   ├── cartStore.js
│   │   └── orderStore.js
│   ├── api/
│   │   └── orders.js         # API 呼叫封裝
│   ├── App.jsx
│   └── main.jsx
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

---

## 頁面設計

### 1. 首頁 `/` - 商品列表

```
┌──────────────────────────────────────────┐
│  🛒 智慧配送商店              [購物車 3] │
├──────────────────────────────────────────┤
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐     │
│  │ 📦  │  │ 📦  │  │ 📦  │  │ 📦  │     │
│  │商品A│  │商品B│  │商品C│  │商品D│     │
│  │$100 │  │$200 │  │$150 │  │$300 │     │
│  │[加入]│  │[加入]│  │[加入]│  │[加入]│     │
│  └─────┘  └─────┘  └─────┘  └─────┘     │
└──────────────────────────────────────────┘
```

### 2. 購物車 `/cart`

```
┌──────────────────────────────────────────┐
│  購物車                                  │
├──────────────────────────────────────────┤
│  商品A          x2          $200   [刪除]│
│  商品B          x1          $200   [刪除]│
├──────────────────────────────────────────┤
│  總計                       $400         │
│                        [前往結帳]        │
└──────────────────────────────────────────┘
```

### 3. 結帳 `/checkout`

```
┌──────────────────────────────────────────┐
│  選擇取貨地點                            │
├──────────────────────────────────────────┤
│  ○ A 點 - 大門口                         │
│  ● D 點 - 圖書館                         │
│  ○ X1 點 - 中庭                          │
├──────────────────────────────────────────┤
│                        [確認下單]        │
└──────────────────────────────────────────┘
```

### 4. 訂單追蹤 `/tracking/:orderId`

```
┌──────────────────────────────────────────┐
│  訂單 #O1a2b3c4                          │
│  狀態: 🚗 配送中                         │
├──────────────────────────────────────────┤
│                                          │
│    A ━━━━● X1 ──── X2 ──── D            │
│          🚗                              │
│    進度: 40%   預計: 10 秒後抵達         │
│                                          │
└──────────────────────────────────────────┘
```

---

## 即時地圖實作

### 地圖資料格式

```json
{
  "map_id": "campus_demo",
  "nodes": [
    { "id": "A", "x": 0, "y": 0 },
    { "id": "X1", "x": 50, "y": 0 },
    { "id": "X2", "x": 100, "y": 0 },
    { "id": "D", "x": 150, "y": 0 }
  ],
  "edges": [
    { "from": "A", "to": "X1" },
    { "from": "X1", "to": "X2" },
    { "from": "X2", "to": "D" }
  ]
}
```

### Canvas 繪製邏輯

```jsx
// LiveMap.jsx
function LiveMap({ mapData, robotPosition }) {
  const canvasRef = useRef(null);
  
  useEffect(() => {
    const ctx = canvasRef.current.getContext('2d');
    const scale = 4; // 1cm = 4px
    
    // 清空
    ctx.clearRect(0, 0, 800, 400);
    
    // 畫路線
    ctx.strokeStyle = '#ccc';
    ctx.lineWidth = 3;
    mapData.edges.forEach(edge => {
      const from = mapData.nodes.find(n => n.id === edge.from);
      const to = mapData.nodes.find(n => n.id === edge.to);
      ctx.beginPath();
      ctx.moveTo(from.x * scale + 50, 200);
      ctx.lineTo(to.x * scale + 50, 200);
      ctx.stroke();
    });
    
    // 畫節點
    mapData.nodes.forEach(node => {
      ctx.fillStyle = '#333';
      ctx.beginPath();
      ctx.arc(node.x * scale + 50, 200, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillText(node.id, node.x * scale + 45, 230);
    });
    
    // 畫小車
    if (robotPosition) {
      ctx.fillStyle = '#f00';
      ctx.beginPath();
      ctx.arc(robotPosition.x * scale + 50, 200, 12, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [mapData, robotPosition]);
  
  return <canvas ref={canvasRef} width={800} height={400} />;
}
```

---

## WebSocket 整合

### 連線 Hook

```javascript
// hooks/useWebSocket.js
import { useEffect, useRef, useState } from 'react';

export function useWebSocket(orderId) {
  const ws = useRef(null);
  const [robotState, setRobotState] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    ws.current = new WebSocket(`ws://${location.host}/ws`);
    
    ws.current.onopen = () => {
      setConnected(true);
      ws.current.send(JSON.stringify({
        type: 'subscribe',
        payload: { order_id: orderId }
      }));
    };
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'order_update' && data.order_id === orderId) {
        setRobotState({
          node: data.node,
          progress: data.progress,
          speed: data.speed,
          state: data.state
        });
      }
    };
    
    ws.current.onclose = () => setConnected(false);
    
    return () => ws.current?.close();
  }, [orderId]);

  return { robotState, connected };
}
```

### 計算小車位置

```javascript
// 根據 node 和 progress 計算座標
function calculateRobotPosition(mapData, route, currentNode, progress) {
  const nodeIndex = route.indexOf(currentNode);
  if (nodeIndex === -1 || nodeIndex >= route.length - 1) {
    const node = mapData.nodes.find(n => n.id === currentNode);
    return { x: node.x, y: node.y };
  }
  
  const from = mapData.nodes.find(n => n.id === route[nodeIndex]);
  const to = mapData.nodes.find(n => n.id === route[nodeIndex + 1]);
  
  return {
    x: from.x + (to.x - from.x) * progress,
    y: from.y + (to.y - from.y) * progress
  };
}
```

---

## API 呼叫

```javascript
// api/orders.js
const API_BASE = '/api';

export async function createOrder(mapId, fromNode, toNode) {
  const res = await fetch(`${API_BASE}/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      map_id: mapId,
      from_node: fromNode,
      to_node: toNode
    })
  });
  return res.json();
}

export async function getOrder(orderId) {
  const res = await fetch(`${API_BASE}/orders/${orderId}`);
  return res.json();
}
```

---

## 開發時程

| 週次 | 任務 | 產出 |
|------|------|------|
| W1 | 環境建置 | Vite 專案、Tailwind 設定、Router |
| W2 | 商品頁面 | Home、ProductCard、mock 商品資料 |
| W3 | 購物車 | CartDrawer、Zustand store |
| W4 | 訂單流程 | Checkout、API 串接 |
| W5 | 即時地圖 | LiveMap、WebSocket hook |
| W6 | 整合測試 | 與後端聯調、Demo 準備 |

---

## 與後端協作

### 我需要後端提供

- [x] REST API：`POST /orders`、`GET /orders/:id`
- [x] WebSocket：`ws://host/ws`
- [ ] 商品列表 API（或用 mock 資料）
- [ ] 地圖資料 API（或直接用 `data/map.json`）

### 聯調前準備

1. 確認後端 IP 和 Port
2. 更新 Nginx 反向代理設定
3. 測試 API 連通性

---

## 本機開發指令

```bash
# 建立專案
npm create vite@latest frontend -- --template react
cd frontend
npm install

# 安裝依賴
npm install zustand react-router-dom

# Tailwind
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# 開發
npm run dev

# 建置
npm run build
```

---

## 待辦事項

- [ ] 建立 Vite 專案
- [ ] 設定 Tailwind CSS
- [ ] 刻 ProductCard 元件
- [ ] 實作購物車 store
- [ ] 刻 LiveMap 元件
- [ ] 實作 WebSocket hook
- [ ] 與後端聯調測試
