// 把買家下單的任意座標 (x,y)「吸附到最近的道路線段」上，生成一個「虛擬節點 Virtual Node」，再把它當成 drop 點丟進同一套 Planner。
// 動態接單就是：每次新增訂單就用目前狀態重新規劃一次（replan）。
// 測試方法:
// add 1 140 140
// plan
// add 7 170 120
// plan
// add 3 100 200
// plan
// quit

#include <bits/stdc++.h>
using namespace std;

struct Edge { int to; long long w; };
static const long long INF = (1LL<<60);

static inline long long llroundll(double x){ return (long long) llround(x); }

vector<long long> dijkstra(int n, const vector<vector<Edge>>& g, int src) {
    vector<long long> dist(n, INF);
    priority_queue<pair<long long,int>, vector<pair<long long,int>>, greater<pair<long long,int>>> pq;
    dist[src] = 0;
    pq.push({0, src});
    while(!pq.empty()){
        auto [d,u] = pq.top(); pq.pop();
        if(d != dist[u]) continue;
        for(auto &e: g[u]){
            if(dist[e.to] > d + e.w){
                dist[e.to] = d + e.w;
                pq.push({dist[e.to], e.to});
            }
        }
    }
    return dist;
}

// ---------- Map / Graph with geometry ----------
struct MapGraph {
    vector<pair<double,double>> coord;          // node -> (x,y) in cm
    vector<vector<Edge>> g;                    // adjacency
    vector<pair<int,int>> undirectedEdges;     // store each edge once (u<v)

    int addNode(double x, double y){
        int id = (int)coord.size();
        coord.push_back({x,y});
        g.push_back({});
        return id;
    }

    void addUndirectedEdge(int u, int v, long long w){
        g[u].push_back({v,w});
        g[v].push_back({u,w});
        if(u>v) swap(u,v);
        undirectedEdges.push_back({u,v});
    }

    static long long distL1(double ax,double ay,double bx,double by){
        // On grid roads we use manhattan along segments; but edge weights already reflect axis distance.
        return (long long) llround(fabs(ax-bx) + fabs(ay-by));
    }

    // Project point P onto segment AB (works for any segment; your map edges are axis-aligned)
    static pair<double,double> closestPointOnSegment(double px,double py,
                                                     double ax,double ay,
                                                     double bx,double by)
    {
        double vx = bx-ax, vy = by-ay;
        double wx = px-ax, wy = py-ay;
        double vv = vx*vx + vy*vy;
        if(vv <= 1e-12) return {ax,ay}; // A==B
        double t = (wx*vx + wy*vy) / vv;
        if(t < 0) t = 0;
        if(t > 1) t = 1;
        return {ax + t*vx, ay + t*vy};
    }

    // Snap (x,y) to nearest ROAD SEGMENT (edge). Create virtual node at the closest point.
    int addVirtualNodeSnappedToRoad(double x, double y){
        double bestD2 = 1e100;
        int bestU=-1, bestV=-1;
        pair<double,double> bestQ{0,0};

        for(auto [u,v] : undirectedEdges){
            auto [ax,ay] = coord[u];
            auto [bx,by] = coord[v];
            auto q = closestPointOnSegment(x,y,ax,ay,bx,by);
            double dx = x - q.first, dy = y - q.second;
            double d2 = dx*dx + dy*dy;
            if(d2 < bestD2){
                bestD2 = d2;
                bestU = u; bestV = v;
                bestQ = q;
            }
        }

        // Create virtual node at bestQ
        int vid = addNode(bestQ.first, bestQ.second);

        // Connect to endpoints with weights equal to segment distance
        auto [ux,uy] = coord[bestU];
        auto [vx,vy] = coord[bestV];
        long long wU = distL1(bestQ.first, bestQ.second, ux, uy);
        long long wV = distL1(bestQ.first, bestQ.second, vx, vy);

        addUndirectedEdge(vid, bestU, wU);
        addUndirectedEdge(vid, bestV, wV);

        return vid;
    }

    void printNodes() const {
        cout << "Nodes (id -> (x,y) cm):\n";
        for(int i=0;i<(int)coord.size();i++){
            cout << "  " << i << " -> (" << coord[i].first << "," << coord[i].second << ")\n";
        }
        cout << "\n";
    }
};

// ---------- Planner (fixed delivery order, flexible pickup order) ----------
static inline uint64_t packState(uint32_t posIdx, uint32_t k, uint32_t mask){
    return (uint64_t)posIdx | ((uint64_t)k << 10) | ((uint64_t)mask << 16);
}
static inline void unpackState(uint64_t key, uint32_t &posIdx, uint32_t &k, uint32_t &mask){
    posIdx = (uint32_t)(key & ((1u<<10)-1));
    k      = (uint32_t)((key >> 10) & ((1u<<6)-1));
    mask   = (uint32_t)(key >> 16);
}

struct ParentInfo {
    uint64_t prevKey;
    string action;
    int movedToGraphNode;
};

struct PQNode {
    long long cost;
    uint64_t key;
    bool operator>(const PQNode& o) const { return cost > o.cost; }
};

struct Planner {
    const MapGraph &mp;
    int startNode;
    int nOrders;
    vector<int> shop, drop; // 1-indexed

    // important points: [0]=current start, [1..n]=shop(i), [n+1..2n]=drop(i)
    vector<int> imp;
    vector<vector<long long>> distFromImp;

    Planner(const MapGraph &map, int start,
            const vector<pair<int,int>>& orders /* (shopNode, dropNode) */)
        : mp(map)
    {
        startNode = start;
        nOrders = (int)orders.size();
        shop.assign(nOrders+1, -1);
        drop.assign(nOrders+1, -1);
        for(int i=1;i<=nOrders;i++){
            shop[i] = orders[i-1].first;
            drop[i] = orders[i-1].second;
        }

        imp.reserve(1 + 2*nOrders);
        imp.push_back(startNode);
        for(int i=1;i<=nOrders;i++) imp.push_back(shop[i]);
        for(int i=1;i<=nOrders;i++) imp.push_back(drop[i]);

        int K = (int)imp.size();
        distFromImp.resize(K);
        for(int i=0;i<K;i++){
            distFromImp[i] = dijkstra((int)mp.g.size(), mp.g, imp[i]);
        }
    }

    long long distImp(int aIdx, int bIdx) const {
        return distFromImp[aIdx][ imp[bIdx] ];
    }
    int shopIdx(int i) const { return i; }
    int dropIdx(int i) const { return nOrders + i; }

    // 支援動態：可以從 (currentPos, nextDeliverK, pickedMask) 重新規劃
    // 注意：pickedMask bit(i-1)=1 表示 i 已取未送；nextDeliverK 表示下一個必須送的訂單編號
    bool solveFromState(int nextDeliverK, uint32_t pickedMask,
                        vector<string> &outActions,
                        vector<int> &outStops,
                        long long &outCost)
    {
        outActions.clear();
        outStops.clear();
        outCost = -1;

        if(nOrders > 20) return false;
        if(nextDeliverK < 1) nextDeliverK = 1;
        if(nextDeliverK > nOrders+1) nextDeliverK = nOrders+1;

        uint32_t initPos = 0;
        uint32_t initK = (uint32_t)nextDeliverK;
        uint32_t initMask = pickedMask;
        uint64_t initKey = packState(initPos, initK, initMask);

        unordered_map<uint64_t, long long> best;
        unordered_map<uint64_t, ParentInfo> parent;
        best.reserve(1<<16);
        parent.reserve(1<<16);

        priority_queue<PQNode, vector<PQNode>, greater<PQNode>> pq;
        best[initKey] = 0;
        pq.push({0, initKey});

        uint64_t goalKey = 0;
        bool found = false;

        while(!pq.empty()){
            auto cur = pq.top(); pq.pop();
            long long curCost = cur.cost;
            uint64_t curKey = cur.key;

            auto it = best.find(curKey);
            if(it == best.end() || it->second != curCost) continue;

            uint32_t posIdx, k, mask;
            unpackState(curKey, posIdx, k, mask);

            if(k == (uint32_t)(nOrders+1)){
                goalKey = curKey;
                found = true;
                break;
            }

            // Deliver k if picked
            uint32_t bitK = 1u << (k-1);
            if(mask & bitK){
                int nextPosIdx = dropIdx((int)k);
                long long w = distImp((int)posIdx, nextPosIdx);
                if(w < INF/2){
                    uint32_t nextMask = mask & (~bitK);
                    uint32_t nextK = k+1;
                    uint64_t nextKey = packState((uint32_t)nextPosIdx, nextK, nextMask);
                    long long nextCost = curCost + w;
                    if(!best.count(nextKey) || nextCost < best[nextKey]){
                        best[nextKey] = nextCost;
                        parent[nextKey] = {curKey,
                            "DELIVER order " + to_string(k) + " at node " + to_string(imp[nextPosIdx]),
                            imp[nextPosIdx]
                        };
                        pq.push({nextCost, nextKey});
                    }
                }
            }

            // Pickup any i >= k not picked
            for(uint32_t i=k; i<=(uint32_t)nOrders; i++){
                uint32_t bitI = 1u << (i-1);
                if(mask & bitI) continue;

                int nextPosIdx = shopIdx((int)i);
                long long w = distImp((int)posIdx, nextPosIdx);
                if(w >= INF/2) continue;

                uint32_t nextMask = mask | bitI;
                uint64_t nextKey = packState((uint32_t)nextPosIdx, k, nextMask);
                long long nextCost = curCost + w;

                if(!best.count(nextKey) || nextCost < best[nextKey]){
                    best[nextKey] = nextCost;
                    parent[nextKey] = {curKey,
                        "PICKUP order " + to_string(i) + " at shop node " + to_string(imp[nextPosIdx]),
                        imp[nextPosIdx]
                    };
                    pq.push({nextCost, nextKey});
                }
            }
        }

        if(!found) return false;

        // reconstruct
        vector<string> actions;
        vector<int> stops;
        uint64_t curKey = goalKey;
        while(curKey != initKey){
            auto it = parent.find(curKey);
            if(it == parent.end()) break;
            actions.push_back(it->second.action);
            stops.push_back(it->second.movedToGraphNode);
            curKey = it->second.prevKey;
        }
        reverse(actions.begin(), actions.end());
        reverse(stops.begin(), stops.end());

        outActions = actions;
        outStops = stops;
        outCost = best[goalKey];
        return true;
    }
};

// ---------- Build a 3x3 cross-road grid map (your demo map) ----------
MapGraph buildGrid3x3(){
    MapGraph mp;

    // 9 intersections
    int xs[3] = {60,120,180};
    int ys[3] = {60,135,210};

    auto id = [&](int r,int c){ return r*3+c; };

    for(int r=0;r<3;r++){
        for(int c=0;c<3;c++){
            mp.addNode(xs[c], ys[r]);
        }
    }

    auto add = [&](int a,int b){
        auto [ax,ay]=mp.coord[a];
        auto [bx,by]=mp.coord[b];
        long long w = (long long) llround(fabs(ax-bx)+fabs(ay-by));
        mp.addUndirectedEdge(a,b,w);
    };

    for(int r=0;r<3;r++){
        for(int c=0;c<3;c++){
            int u=id(r,c);
            if(r+1<3) add(u, id(r+1,c));
            if(c+1<3) add(u, id(r,c+1));
        }
    }
    return mp;
}

// ---------- Dynamic simulation ----------
int main(){
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    MapGraph mp = buildGrid3x3();
    cout << "=== Base 3x3 Cross-road Map ===\n";
    mp.printNodes();

    int currentPos = 4;          // start at center intersection
    int nextDeliverK = 1;        // next order to deliver
    uint32_t pickedMask = 0;     // picked but not delivered

    vector<pair<int,int>> orders; // (shopNode, dropNode) in purchase order

    // cout << "Input format:\n";
    // cout << "  shopNode buyerX buyerY   (buyerX,buyerY in cm; can be ANY point)\n";
    // cout << "Commands:\n";
    // cout << "  add <shopNode> <buyerX> <buyerY>   (add a new order)\n";
    // cout << "  plan                               (replan now)\n";
    // cout << "  quit\n\n";

    string cmd;
    while (true) {
        cout << ">> ";
        if(!(cin >> cmd)) break;
        if(cmd == "quit") break;

        if(cmd == "add"){
            int shopNode;
            double bx, by;
            cin >> shopNode >> bx >> by;

            // snap buyer coordinate to nearest ROAD segment, create virtual node
            int dropNode = mp.addVirtualNodeSnappedToRoad(bx, by);

            orders.push_back({shopNode, dropNode});

            cout << "Added order #" << orders.size()
                 << " shop=" << shopNode
                 << " buyer=(" << bx << "," << by << ")"
                 << " snappedDropNode=" << dropNode
                 << " at (" << mp.coord[dropNode].first << "," << mp.coord[dropNode].second << ")\n";
        }
        else if(cmd == "plan"){
            if(orders.empty()){
                cout << "No orders.\n";
                continue;
            }

            // replan from current state
            Planner planner(mp, currentPos, orders);

            vector<string> actions;
            vector<int> stops;
            long long bestCost;

            bool ok = planner.solveFromState(nextDeliverK, pickedMask, actions, stops, bestCost);
            if(!ok){
                cout << "No feasible plan found.\n";
                continue;
            }

            cout << "\n=== Replan Result ===\n";
            cout << "Orders=" << orders.size()
                 << ", nextDeliverK=" << nextDeliverK
                 << ", pickedMask=" << pickedMask
                 << ", currentPos=" << currentPos << "\n";
            cout << "Best total distance (cm) from CURRENT STATE = " << bestCost << "\n";
            for(size_t i=0;i<actions.size();i++){
                cout << (i+1) << ". " << actions[i] << "\n";
            }
            cout << "Stops visit order:\n";
            cout << currentPos;
            for(int v: stops) cout << " -> " << v;
            cout << "\n\n";
        }
        else{
            cout << "Unknown command.\n";
        }
    }

    return 0;
}
