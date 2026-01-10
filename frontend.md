# 前端購物平台與即時地圖顯示

> 模組二 | 更新日期：2026/01/10

---

## 我的職責範圍

根據分工文件，我負責(廖紀翔)：

- [ ] 使用者購物平台介面設計（Uber Eats 風格）
- [ ] **多店家列表與店家頁面**
- [ ] 商品列表、商品詳細頁
- [ ] 購物車與訂單建立流程
- [ ] **使用者註冊/登入系統**
- [ ] **配送地址管理（新增/編輯/選擇）**
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
│   └── map.json              # 地圖資料
├── src/
│   ├── components/
│   │   ├── Navbar.jsx
│   │   ├── StoreCard.jsx     # 店家卡片
│   │   ├── ProductCard.jsx   # 商品卡片
│   │   ├── CartDrawer.jsx    # 購物車側邊欄
│   │   ├── AddressCard.jsx   # 地址卡片
│   │   ├── AddressForm.jsx   # 新增/編輯地址表單
│   │   ├── OrderStatus.jsx   # 訂單狀態 badge
│   │   ├── LiveMap.jsx       # 即時地圖（核心）
│   │   └── RobotMarker.jsx   # 小車標記
│   ├── pages/
│   │   ├── Home.jsx          # 店家列表
│   │   ├── Store.jsx         # 店家頁面（該店商品）
│   │   ├── Product.jsx       # 商品詳細
│   │   ├── Cart.jsx          # 購物車
│   │   ├── Checkout.jsx      # 結帳（選配送地址）
│   │   ├── Orders.jsx        # 訂單列表
│   │   ├── Tracking.jsx      # 訂單追蹤 + 地圖
│   │   ├── Login.jsx         # 登入
│   │   ├── Register.jsx      # 註冊
│   │   ├── Account.jsx       # 帳號設定
│   │   └── Addresses.jsx     # 地址管理
│   ├── hooks/
│   │   ├── useWebSocket.js   # WS 連線
│   │   ├── useAuth.js        # 認證邏輯
│   │   └── useCart.js        # 購物車邏輯
│   ├── stores/
│   │   ├── authStore.js      # 使用者狀態
│   │   ├── cartStore.js      # 購物車狀態
│   │   └── orderStore.js     # 訂單狀態
│   ├── api/
│   │   ├── auth.js           # 登入/註冊 API
│   │   ├── stores.js         # 店家 API
│   │   ├── orders.js         # 訂單 API
│   │   └── addresses.js      # 地址 API
│   ├── App.jsx
│   └── main.jsx
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

---

## 頁面設計

### 1. 首頁 `/` - 店家列表

```
+------------------------------------------+
|  DeliveryBot         [登入] [購物車 3]   |
+------------------------------------------+
|  分類: [全部] [餐廳] [飲料] [便利商店]   |
+------------------------------------------+
|  +--------+  +--------+  +--------+      |
|  | 店家A  |  | 店家B  |  | 店家C  |      |
|  | 餐廳   |  | 飲料   |  | 便利店 |      |
|  | 4.5★  |  | 4.8★  |  | 4.2★  |      |
|  +--------+  +--------+  +--------+      |
+------------------------------------------+
```

### 2. 店家頁面 `/store/:storeId`

```
+------------------------------------------+
|  < 返回                      [購物車 3]  |
+------------------------------------------+
|  店家A - 美味餐廳                        |
|  ★ 4.5 | 配送約 5 分鐘                   |
+------------------------------------------+
|  +------+  +------+  +------+  +------+  |
|  | 商品A|  | 商品B|  | 商品C|  | 商品D|  |
|  | $100 |  | $200 |  | $150 |  | $300 |  |
|  |[加入]|  |[加入]|  |[加入]|  |[加入]|  |
|  +------+  +------+  +------+  +------+  |
+------------------------------------------+
```

### 3. 購物車 `/cart`

```
+------------------------------------------+
|  購物車                                  |
+------------------------------------------+
|  店家A                                   |
|  商品A          x2          $200   [X]   |
|  商品B          x1          $200   [X]   |
+------------------------------------------+
|  總計                       $400         |
|                        [前往結帳]        |
+------------------------------------------+
```

### 4. 結帳 `/checkout`

```
+------------------------------------------+
|  結帳                                    |
+------------------------------------------+
|  配送地址                    [管理地址]  |
|  +------------------------------------+  |
|  | (*) 住家 - 資工系館 3F (節點: D)   |  |
|  | ( ) 公司 - 電機系館 1F (節點: X2)  |  |
|  | [+ 新增地址]                       |  |
|  +------------------------------------+  |
+------------------------------------------+
|  訂單明細                                |
|  商品A x2                    $200        |
|  商品B x1                    $200        |
|  ----------------------------------------|
|  總計                        $400        |
|                        [確認下單]        |
+------------------------------------------+
```

### 5. 訂單追蹤 `/orders/:orderId`

```
+------------------------------------------+
|  訂單 #O1a2b3c4                          |
|  狀態: 配送中                            |
+------------------------------------------+
|                                          |
|    A ====@ X1 ---- X2 ---- D             |
|          ^                               |
|    進度: 40%   預計: 10 秒後抵達         |
|                                          |
+------------------------------------------+
|  配送至: 住家 - 資工系館 3F              |
+------------------------------------------+
```

### 6. 登入 `/login`

```
+------------------------------------------+
|  登入                                    |
+------------------------------------------+
|  Email:    [________________]            |
|  密碼:     [________________]            |
|                                          |
|            [登入]                        |
|                                          |
|  還沒有帳號？ [註冊]                     |
+------------------------------------------+
```

### 7. 地址管理 `/account/addresses`

```
+------------------------------------------+
|  我的地址                                |
+------------------------------------------+
|  +------------------------------------+  |
|  | 住家 (預設)                [編輯]  |  |
|  | 資工系館 3F                        |  |
|  | 節點: D                            |  |
|  +------------------------------------+  |
|  +------------------------------------+  |
|  | 公司                       [編輯]  |  |
|  | 電機系館 1F                        |  |
|  | 節點: X2                           |  |
|  +------------------------------------+  |
|                                          |
|  [+ 新增地址]                            |
+------------------------------------------+
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

### 認證 API

```javascript
// api/auth.js
const API_BASE = '/api';

export async function register(email, password, name) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name })
  });
  return res.json();
}

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  return res.json(); // { token, user }
}

export async function getMe(token) {
  const res = await fetch(`${API_BASE}/users/me`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return res.json();
}
```

### 店家 API

```javascript
// api/stores.js
export async function getStores() {
  const res = await fetch(`${API_BASE}/stores`);
  return res.json();
}

export async function getStore(storeId) {
  const res = await fetch(`${API_BASE}/stores/${storeId}`);
  return res.json();
}

export async function getStoreProducts(storeId) {
  const res = await fetch(`${API_BASE}/stores/${storeId}/products`);
  return res.json();
}
```

### 地址 API

```javascript
// api/addresses.js
export async function getAddresses(token) {
  const res = await fetch(`${API_BASE}/users/me/addresses`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return res.json();
}

export async function createAddress(token, address) {
  const res = await fetch(`${API_BASE}/users/me/addresses`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(address)
  });
  return res.json();
}
```

### 訂單 API

```javascript
// api/orders.js
export async function createOrder(token, storeId, items, addressId) {
  const res = await fetch(`${API_BASE}/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      store_id: storeId,
      items: items,
      delivery_address_id: addressId
    })
  });
  return res.json();
}

export async function getOrders(token) {
  const res = await fetch(`${API_BASE}/orders`, {
    headers: { 'Authorization': `Bearer ${token}` }
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
| W1 | 環境建置 | Vite 專案、Tailwind、Router、店家 mock 資料 |
| W2 | 店家與商品頁面 | Home (StoreCard)、Store (ProductCard) |
| W3 | 購物車 | CartDrawer、Zustand store |
| W4 | 帳號系統 | Login、Register、authStore、JWT 處理 |
| W5 | 地址管理 | AddressForm、Addresses 頁面 |
| W6 | 訂單流程 | Checkout、建立訂單 API 串接 |
| W7 | 即時地圖 | LiveMap、WebSocket hook |
| W8 | 整合測試 | 與後端聯調、Demo 準備 |

---

## 與後端協作

### 我需要後端提供

- [x] REST API：`POST /orders`、`GET /orders/:id`
- [x] WebSocket：`ws://host/ws`
- [ ] 認證 API：`POST /auth/login`、`POST /auth/register`
- [ ] 使用者 API：`GET /users/me`
- [ ] 地址 API：`GET/POST /users/me/addresses`
- [ ] 店家 API：`GET /stores`、`GET /stores/:id/products`
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

### Phase 1 - 環境與基礎
- [ ] 建立 Vite 專案
- [ ] 設定 Tailwind CSS
- [ ] 設定 React Router

### Phase 2 - 店家與商品
- [ ] 刻 StoreCard 元件
- [ ] 刻 ProductCard 元件
- [ ] 實作 Home 頁面（店家列表）
- [ ] 實作 Store 頁面（店家商品）

### Phase 3 - 購物車
- [ ] 實作 cartStore (Zustand)
- [ ] 刻 CartDrawer 元件

### Phase 4 - 帳號系統
- [ ] 實作 authStore (JWT 處理)
- [ ] 刻 Login 頁面
- [ ] 刻 Register 頁面

### Phase 5 - 地址管理
- [ ] 刻 AddressCard 元件
- [ ] 刻 AddressForm 元件
- [ ] 實作 Addresses 頁面

### Phase 6 - 訂單流程
- [ ] 刻 Checkout 頁面（選地址）
- [ ] 建立訂單 API 串接

### Phase 7 - 即時地圖
- [ ] 刻 LiveMap 元件
- [ ] 實作 WebSocket hook
- [ ] 實作 Tracking 頁面

### Phase 8 - 整合測試
- [ ] 與後端聯調測試
- [ ] Demo 準備

