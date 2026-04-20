"""
Plan Executor

Bridges robot/{robot_id}/plan → car/cmd

Flow:
  1. Receive plan (stops list) from planner via MQTT
  2. Expand stops into full node path using dijkstra
  3. When car reports position via car/node_id (AprilTag confirmed),
     compute direction and send car/cmd
"""

import logging
import threading
from typing import Optional, List

logger = logging.getLogger(__name__)


class PlanExecutor:
    def __init__(self):
        self._lock = threading.Lock()
        self.full_path: List[str] = []
        self.pickup_nodes: set = set()
        self.current_step: int = 0
        self.prev_node: Optional[str] = None
        self.current_node: Optional[str] = None
        self._active: bool = False

    def on_new_plan(self, topic: str, payload: dict):
        stops: List[str] = payload.get("stops", [])
        actions: List[str] = payload.get("actions", [])

        if not stops:
            logger.warning("PlanExecutor: received empty plan, ignoring")
            return

        # Identify pickup nodes (need wait_weight)
        pickup_nodes = set()
        for i, action in enumerate(actions):
            if "PICKUP" in action and i < len(stops):
                pickup_nodes.add(stops[i])

        full_path = self._compute_full_path(stops)

        with self._lock:
            self.full_path = full_path
            self.pickup_nodes = pickup_nodes
            self.current_step = 0
            self._active = True

        logger.info(f"PlanExecutor: new plan path={full_path}, pickups={pickup_nodes}")
        self._publish("car/cmd", {"cmd": "forward", "speed": 100})

    def on_node_update(self, topic: str, payload: dict):
        """Car confirmed its position via AprilTag (car/node_id)"""
        node = str(payload.get("tag_id", payload.get("node", ""))).strip()
        if not node:
            return

        with self._lock:
            self.prev_node = self.current_node
            self.current_node = node
            full_path = self.full_path
            active = self._active

        if not active or not full_path:
            return

        logger.info(f"PlanExecutor: car at node {node}")

        # Sync step index to current node position in path
        if node in full_path:
            idx = full_path.index(node)
            with self._lock:
                self.current_step = idx

        # Check if pickup node — wait for package
        with self._lock:
            is_pickup = node in self.pickup_nodes

        if is_pickup:
            logger.info(f"PlanExecutor: pickup at {node}, sending wait_weight")
            self._publish("car/cmd", {"cmd": "wait_weight", "speed": 0})
            with self._lock:
                self.pickup_nodes.discard(node)
            return

        self._send_next_direction()

    def _send_next_direction(self):
        with self._lock:
            step = self.current_step
            full_path = self.full_path
            prev = self.prev_node
            current = self.current_node

        if not full_path or step >= len(full_path) - 1:
            logger.info("PlanExecutor: plan complete, stopping car")
            self._publish("car/cmd", {"cmd": "stop", "speed": 0})
            with self._lock:
                self._active = False
            return

        next_node = full_path[step + 1]
        cmd = self._determine_direction(prev, current, next_node)
        logger.info(f"PlanExecutor: {prev}→{current}→{next_node} = {cmd}")
        self._publish("car/cmd", {"cmd": cmd, "speed": 100})

    def _compute_full_path(self, stops: List[str]) -> List[str]:
        from .graph import dijkstra
        from .state import GRAPH_STORE

        graph = next(iter(GRAPH_STORE.values()), None)
        if not graph or len(stops) < 2:
            return stops

        full_path: List[str] = []
        for i in range(len(stops) - 1):
            try:
                path, _ = dijkstra(graph, stops[i], stops[i + 1])
                if full_path:
                    full_path.extend(path[1:])
                else:
                    full_path.extend(path)
            except Exception as e:
                logger.error(f"PlanExecutor: dijkstra failed {stops[i]}→{stops[i+1]}: {e}")
                return stops

        return full_path

    def _determine_direction(self, prev: Optional[str], current: Optional[str], next_node: str) -> str:
        """
        Cross product of (prev→current) and (current→next) vectors.
        Positive cross = left, negative = right, zero = forward/backward.
        """
        if not prev or not current:
            return "forward"

        from .state import MAP_STORE
        map_data = next(iter(MAP_STORE.values()), None)
        if not map_data:
            return "forward"

        coords = {n.id: (n.x, n.y) for n in map_data.nodes}
        if prev not in coords or current not in coords or next_node not in coords:
            return "forward"

        px, py = coords[prev]
        cx, cy = coords[current]
        nx, ny = coords[next_node]

        hx, hy = cx - px, cy - py   # heading vector
        dx, dy = nx - cx, ny - cy   # next direction vector

        cross = hx * dy - hy * dx
        if cross > 0:
            return "left"
        elif cross < 0:
            return "right"
        else:
            return "forward" if (hx * dx + hy * dy) >= 0 else "backward"

    def _publish(self, topic: str, payload: dict):
        from .mqtt_bridge import get_mqtt_bridge
        bridge = get_mqtt_bridge()
        bridge.client.publish(topic, payload)


_executor: Optional[PlanExecutor] = None


def get_plan_executor() -> PlanExecutor:
    global _executor
    if _executor is None:
        _executor = PlanExecutor()
    return _executor
