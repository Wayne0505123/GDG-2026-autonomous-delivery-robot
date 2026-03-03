"""
Python 實現的動態路徑規劃演算法
移植自 algorithm.cpp

核心功能：
1. MapGraph：地圖與圖結構，支持任意座標吸附到最近的道路段上（virtual node）
2. Planner：VRP problem solver，支持動態接單和重新規劃
3. 約束：固定接送順序（pick order 1, deliver 1, pick 2, deliver 2, ...）

注意：位置單位為 cm，距離使用曼哈頓距離
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
import heapq
import math

INF = 1 << 60  # 無限大


@dataclass
class Edge:
    to: int
    weight: int


@dataclass
class ParentInfo:
    prev_key: int
    action: str
    moved_to_node: int


def dist_l1(ax: float, ay: float, bx: float, by: float) -> int:
    """曼哈頓距離"""
    return int(round(abs(ax - bx) + abs(ay - by)))


def closest_point_on_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> Tuple[float, float]:
    """
    計算點 P 投影到線段 AB 上的最近點。
    返回該投影點的座標。
    """
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    vv = vx * vx + vy * vy

    if vv <= 1e-12:
        return (ax, ay)

    t = (wx * vx + wy * vy) / vv
    t = max(0.0, min(1.0, t))

    return (ax + t * vx, ay + t * vy)


class MapGraph:
    """地圖與圖結構，支持虛擬節點吸附"""

    def __init__(self):
        self.coord: List[Tuple[float, float]] = []  # node_id -> (x, y) in cm
        self.graph: List[List[Edge]] = []  # adjacency list
        self.undirected_edges: List[Tuple[int, int]] = []  # store each edge once (u < v)

    def add_node(self, x: float, y: float) -> int:
        """添加節點，返回節點 ID"""
        node_id = len(self.coord)
        self.coord.append((x, y))
        self.graph.append([])
        return node_id

    def add_undirected_edge(self, u: int, v: int, weight: int) -> None:
        """添加無向邊"""
        self.graph[u].append(Edge(v, weight))
        self.graph[v].append(Edge(u, weight))
        if u > v:
            u, v = v, u
        self.undirected_edges.append((u, v))

    def dijkstra(self, src: int) -> List[int]:
        """
        從源點 src 運行 Dijkstra，返回所有節點的最短距離。
        """
        n = len(self.coord)
        dist = [INF] * n
        dist[src] = 0
        pq = [(0, src)]

        while pq:
            d, u = heapq.heappop(pq)
            if d != dist[u]:
                continue

            for edge in self.graph[u]:
                if dist[edge.to] > d + edge.weight:
                    dist[edge.to] = d + edge.weight
                    heapq.heappush(pq, (dist[edge.to], edge.to))

        return dist

    def add_virtual_node_snapped_to_road(self, x: float, y: float) -> int:
        """
        將任意座標 (x, y) 吸附到最近的道路段上，創建虛擬節點。
        返回該虛擬節點的 ID。
        """
        best_dist2 = float("inf")
        best_u = -1
        best_v = -1
        best_q = (0.0, 0.0)

        for u, v in self.undirected_edges:
            ax, ay = self.coord[u]
            bx, by = self.coord[v]
            qx, qy = closest_point_on_segment(x, y, ax, ay, bx, by)

            dx, dy = x - qx, y - qy
            d2 = dx * dx + dy * dy

            if d2 < best_dist2:
                best_dist2 = d2
                best_u = u
                best_v = v
                best_q = (qx, qy)

        # 在最近點創建虛擬節點
        vid = self.add_node(best_q[0], best_q[1])

        # 連接到線段的兩個端點
        ux, uy = self.coord[best_u]
        vx, vy = self.coord[best_v]
        wu = dist_l1(best_q[0], best_q[1], ux, uy)
        wv = dist_l1(best_q[0], best_q[1], vx, vy)

        self.add_undirected_edge(vid, best_u, wu)
        self.add_undirected_edge(vid, best_v, wv)

        return vid


def pack_state(pos_idx: int, k: int, mask: int) -> int:
    """將 (posIdx, k, mask) 打包為單一狀態值"""
    return pos_idx | (k << 10) | (mask << 16)


def unpack_state(key: int) -> Tuple[int, int, int]:
    """解包狀態值為 (posIdx, k, mask)"""
    pos_idx = key & ((1 << 10) - 1)
    k = (key >> 10) & ((1 << 6) - 1)
    mask = key >> 16
    return pos_idx, k, mask


class Planner:
    """
    VRP Planner：支持動態接單與重新規劃

    狀態空間：(當前位置, 下一個必須送的訂單號, 已取未送的掩碼)
    約束：固定接送順序 (pick 1, deliver 1, pick 2, deliver 2, ...)
    """

    def __init__(self, map_graph: MapGraph, start_node: int, orders: List[Tuple[int, int]]):
        """
        初始化 Planner

        :param map_graph: MapGraph 實例
        :param start_node: 起始節點 ID
        :param orders: 訂單列表，每項為 (shop_node_id, drop_node_id)
        """
        self.mp = map_graph
        self.start_node = start_node
        self.n_orders = len(orders)

        # shop[1..n], drop[1..n]
        self.shop = [-1] * (self.n_orders + 1)
        self.drop = [-1] * (self.n_orders + 1)
        for i, (s, d) in enumerate(orders, 1):
            self.shop[i] = s
            self.drop[i] = d

        # important points: [0]=start, [1..n]=shop(i), [n+1..2n]=drop(i)
        self.imp = [start_node]
        for i in range(1, self.n_orders + 1):
            self.imp.append(self.shop[i])
        for i in range(1, self.n_orders + 1):
            self.imp.append(self.drop[i])

        # 預計算所有重要點之間的距離
        self.dist_from_imp: List[List[int]] = []
        for imp_node in self.imp:
            self.dist_from_imp.append(self.mp.dijkstra(imp_node))

    def dist_imp(self, a_idx: int, b_idx: int) -> int:
        """從重要點 a_idx 到 b_idx 的最短距離"""
        return self.dist_from_imp[a_idx][self.imp[b_idx]]

    def shop_idx(self, i: int) -> int:
        """訂單 i 的 shop 在 imp 中的索引"""
        return i

    def drop_idx(self, i: int) -> int:
        """訂單 i 的 drop 在 imp 中的索引"""
        return self.n_orders + i

    def solve_from_state(
        self, next_deliver_k: int, picked_mask: int
    ) -> Tuple[bool, List[str], List[int], int]:
        """
        從當前狀態開始動態規劃求解

        :param next_deliver_k: 下一個必須送的訂單號 (1-indexed)
        :param picked_mask: 已取未送的掩碼 (bit i-1 = 訂單 i)
        :return: (可行性, 動作列表, 拜訪節點列表, 總成本)
        """
        if self.n_orders > 20:
            return False, [], [], -1

        next_deliver_k = max(1, min(self.n_orders + 1, next_deliver_k))

        init_pos = 0
        init_k = next_deliver_k
        init_mask = picked_mask
        init_key = pack_state(init_pos, init_k, init_mask)

        best = {init_key: 0}
        parent: Dict[int, ParentInfo] = {}
        pq = [(0, init_key)]

        goal_key = 0
        found = False

        while pq:
            cur_cost, cur_key = heapq.heappop(pq)

            if cur_key not in best or best[cur_key] != cur_cost:
                continue

            pos_idx, k, mask = unpack_state(cur_key)

            # 到達目標狀態：所有訂單都已送出
            if k == self.n_orders + 1:
                goal_key = cur_key
                found = True
                break

            # 動作1：送出訂單 k（如果已取）
            bit_k = 1 << (k - 1)
            if mask & bit_k:
                next_pos_idx = self.drop_idx(k)
                w = self.dist_imp(pos_idx, next_pos_idx)
                if w < INF // 2:
                    next_mask = mask & (~bit_k)
                    next_k = k + 1
                    next_key = pack_state(next_pos_idx, next_k, next_mask)
                    next_cost = cur_cost + w

                    if next_key not in best or next_cost < best[next_key]:
                        best[next_key] = next_cost
                        parent[next_key] = ParentInfo(
                            cur_key,
                            f"DELIVER order {k} at node {self.imp[next_pos_idx]}",
                            self.imp[next_pos_idx],
                        )
                        heapq.heappush(pq, (next_cost, next_key))

            # 動作2：取出任何訂單 i >= k（如果未取）
            for i in range(k, self.n_orders + 1):
                bit_i = 1 << (i - 1)
                if mask & bit_i:
                    continue

                next_pos_idx = self.shop_idx(i)
                w = self.dist_imp(pos_idx, next_pos_idx)
                if w >= INF // 2:
                    continue

                next_mask = mask | bit_i
                next_key = pack_state(next_pos_idx, k, next_mask)
                next_cost = cur_cost + w

                if next_key not in best or next_cost < best[next_key]:
                    best[next_key] = next_cost
                    parent[next_key] = ParentInfo(
                        cur_key,
                        f"PICKUP order {i} at shop node {self.imp[next_pos_idx]}",
                        self.imp[next_pos_idx],
                    )
                    heapq.heappush(pq, (next_cost, next_key))

        if not found:
            return False, [], [], -1

        # 重建路徑
        actions = []
        stops = []
        cur_key = goal_key
        while cur_key != init_key:
            if cur_key not in parent:
                break
            info = parent[cur_key]
            actions.append(info.action)
            stops.append(info.moved_to_node)
            cur_key = info.prev_key

        actions.reverse()
        stops.reverse()

        return True, actions, stops, best[goal_key]
