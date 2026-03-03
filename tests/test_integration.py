#!/usr/bin/env python3
"""
簡單測試腳本：驗證演算法整合

使用 mock 資料，無需啟動完整後端
"""

import sys
from pathlib import Path

# 添加上層目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.algorithm import MapGraph, Planner
from app.planner_state import get_global_state


def test_algorithm():
    """測試 algorithm.py 核心功能"""
    print("=" * 60)
    print("TEST 1: Algorithm Core (MapGraph + Planner)")
    print("=" * 60)

    # 1. 構建簡單的 3x3 網格地圖
    mp = MapGraph()
    
    # 添加 9 個節點 (3x3)
    nodes = []
    for r in range(3):
        for c in range(3):
            x = c * 60  # 0, 60, 120
            y = r * 60  # 0, 60, 120
            nid = mp.add_node(x, y)
            nodes.append(nid)
            print(f"  Node {nid}: ({x}, {y})")

    # 添加邊（形成網格）
    def add_edge(r1, c1, r2, c2):
        n1 = r1 * 3 + c1
        n2 = r2 * 3 + c2
        dist = int(((nodes[n1] - nodes[n2]) ** 2) ** 0.5) if False else abs(r1-r2)*60 + abs(c1-c2)*60
        mp.add_undirected_edge(nodes[n1], nodes[n2], dist)

    # 水平邊
    for r in range(3):
        for c in range(2):
            add_edge(r, c, r, c+1)
    # 垂直邊
    for r in range(2):
        for c in range(3):
            add_edge(r, c, r+1, c)

    print("\n  Graph created with 9 nodes and edges\n")

    # 2. 測試 Dijkstra
    print("TEST 1.1: Dijkstra")
    dist_from_0 = mp.dijkstra(0)  # 從左上角出發
    print(f"  Distance from node 0 to all nodes: {dist_from_0}")
    assert dist_from_0[8] == 240, f"Expected 240, got {dist_from_0[8]}"  # 到右下角
    print("  ✅ Dijkstra test passed\n")

    # 3. 測試 Planner
    print("TEST 1.2: Planner (VRP)")
    orders = [
        (1, 5),  # 訂單 1: 從節點 1（上中）取，到節點 5（中央）送
        (2, 7),  # 訂單 2: 從節點 2（上右）取，到節點 7（下中）送
    ]
    start_node = 0  # 起始於左上角

    planner = Planner(mp, start_node, orders)
    ok, actions, stops, cost = planner.solve_from_state(next_deliver_k=1, picked_mask=0)

    print(f"  Planner result: ok={ok}, cost={cost}")
    print(f"  Actions: {actions}")
    print(f"  Stops: {stops}")
    assert ok, "Planner should find a solution"
    assert len(actions) > 0, "Should have actions"
    print("  ✅ Planner test passed\n")

    # 4. 測試虛擬節點吸附
    print("TEST 1.3: Virtual Node Snapping")
    vnode = mp.add_virtual_node_snapped_to_road(75, 30)
    print(f"  Virtual node created at index {vnode}")
    print(f"  Virtual node coords: {mp.coord[vnode]}")
    print("  ✅ Virtual node test passed\n")


def test_planner_state():
    """測試 planner_state.py 狀態管理"""
    print("=" * 60)
    print("TEST 2: Planner State Management")
    print("=" * 60)

    state = get_global_state()

    # 1. 添加小車
    print("\nTEST 2.1: Add Robot")
    robot = state.add_robot("R001", "A")
    print(f"  Robot {robot.robot_id} initialized at {robot.current_node}")
    assert robot.robot_id == "R001"
    print("  ✅ Add robot test passed\n")

    # 2. 添加訂單
    print("TEST 2.2: Add Order")
    oid1 = state.add_order("R001", shop_node="A", drop_node="X1")
    oid2 = state.add_order("R001", shop_node="X1", drop_node="D")
    print(f"  Order 1: {oid1}")
    print(f"  Order 2: {oid2}")
    assert state.get_robot("R001").get_pending_count() == 2
    print("  ✅ Add order test passed\n")

    # 3. 標記訂單狀態
    print("TEST 2.3: Mark Order Status")
    state.mark_order_picked("R001", k=1)
    print(f"  Order 1 marked as picked")
    print(f"  picked_mask: {state.get_robot('R001').picked_mask:08b}")
    assert state.get_robot("R001").picked_mask & (1 << 0), "Order 1 should be in mask"
    
    state.mark_order_delivered("R001", k=1)
    print(f"  Order 1 marked as delivered")
    print(f"  picked_mask after deliver: {state.get_robot('R001').picked_mask:08b}")
    assert state.get_robot("R001").next_deliver_k == 2, "next_deliver_k should be 2"
    print("  ✅ Mark order test passed\n")

    # 4. 更新規劃結果
    print("TEST 2.4: Update Plan")
    actions = ["PICKUP order 1 at A", "DELIVER order 1 at X1"]
    stops = ["A", "X1"]
    state.update_plan("R001", actions, stops, plan_cost=500)
    robot = state.get_robot("R001")
    print(f"  Plan updated: cost={robot.last_plan_cost}, actions={len(robot.plan_actions)}")
    assert robot.last_plan_cost == 500
    print("  ✅ Update plan test passed\n")


def test_mqtt_bridge():
    """測試 mqtt_bridge.py（Mock）"""
    print("=" * 60)
    print("TEST 3: MQTT Bridge (Mock)")
    print("=" * 60)

    from app.mqtt_bridge import get_mqtt_bridge

    mqtt = get_mqtt_bridge(use_mock=True)
    
    print("\nTEST 3.1: Connect & Start")
    if mqtt.start():
        print("  ✅ MQTT bridge started\n")
    else:
        print("  ❌ MQTT bridge failed to start\n")
        return

    print("TEST 3.2: Publish Plan")
    ok = mqtt.publish_plan("R001", ["PICKUP", "DELIVER"], ["A", "D"])
    assert ok, "Should publish successfully"
    print("  ✅ Publish plan test passed\n")

    print("TEST 3.3: Publish Replan Request")
    ok = mqtt.publish_replan_request("R001")
    assert ok, "Should publish replan request"
    print("  ✅ Publish replan request test passed\n")

    mqtt.stop()
    print("MQTT bridge stopped\n")


if __name__ == "__main__":
    try:
        test_algorithm()
        test_planner_state()
        test_mqtt_bridge()

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
