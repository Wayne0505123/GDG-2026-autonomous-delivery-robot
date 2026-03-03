"""
MQTT 橋接層

職責：
1. 連接 MQTT broker
2. 訂閱小車位置與狀態更新 （robot/{robot_id}/telemetry）
3. 發佈規劃指令與重新規劃請求 （robot/{robot_id}/plan）

訊息格式：
  - 小車發佈位置: {"robot_id": "R001", "node": "A", "timestamp": "2026-03-04T..."}
  - 後端發佈規劃: {"order_id": "O1", "actions": [...], "stops": [...]}

未來實現：
  - 使用 paho-mqtt 庫
  - 非同步事件處理
  - 自動重連機制
"""

import logging
from typing import Callable, Dict, Optional
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class MockMQTTClient:
    """
    簡易 Mock MQTT 客戶端（用於開發測試）

    生產環境應改用 paho-mqtt
    """

    def __init__(self, broker_url: str = "mqtt://localhost:1883"):
        self.broker_url = broker_url
        self.is_connected = False
        self.subscriptions: Dict[str, Callable] = {}
        logger.info(f"MockMQTTClient initialized (url={broker_url})")

    def connect(self) -> bool:
        """連接 MQTT broker"""
        logger.info(f"Connecting to {self.broker_url}")
        self.is_connected = True
        return True

    def disconnect(self):
        """斷開連接"""
        self.is_connected = False
        logger.info("Disconnected")

    def subscribe(self, topic: str, callback: Callable) -> bool:
        """訂閱主題"""
        self.subscriptions[topic] = callback
        logger.info(f"Subscribed to {topic}")
        return True

    def publish(self, topic: str, payload: dict) -> bool:
        """發佈訊息"""
        if not self.is_connected:
            logger.warning("Not connected, cannot publish")
            return False

        msg = json.dumps(payload)
        logger.debug(f"Published to {topic}: {msg}")
        return True

    def simulate_receive(self, topic: str, payload: dict):
        """（測試用）模擬接收訊息"""
        if topic in self.subscriptions:
            self.subscriptions[topic](topic, payload)


class MQTTBridge:
    """
    MQTT 橋接層

    向小車、規劃服務系統提供發布/訂閱介面
    """

    def __init__(self, broker_url: str = "mqtt://localhost:1883", use_mock: bool = True):
        """
        初始化 MQTT 橋接

        :param broker_url: MQTT broker URL
        :param use_mock: 是否使用 Mock 客戶端（開發測試）
        """
        self.broker_url = broker_url
        self.use_mock = use_mock

        if use_mock:
            self.client = MockMQTTClient(broker_url)
        else:
            # 未來：改用 paho-mqtt
            # import paho.mqtt.client as mqtt
            # self.client = mqtt.Client()
            raise NotImplementedError("paho-mqtt not yet implemented")

        self.robot_telemetry_callbacks = {}

    def start(self) -> bool:
        """啟動 MQTT 橋接"""
        if not self.client.connect():
            logger.error("Failed to connect to MQTT broker")
            return False

        # 訂閱所有小車的 telemetry 主題 (robot/+/telemetry)
        def on_telemetry(topic: str, payload: dict):
            """小車位置更新回調"""
            logger.info(f"Received telemetry: {payload}")
            robot_id = payload.get("robot_id")
            if robot_id in self.robot_telemetry_callbacks:
                callback = self.robot_telemetry_callbacks[robot_id]
                callback(payload)

        # 為簡單起見，先手動訂閱某個預設主題
        self.client.subscribe("robot/+/telemetry", on_telemetry)
        logger.info("MQTT bridge started")
        return True

    def stop(self):
        """停止 MQTT 橋接"""
        self.client.disconnect()

    def register_telemetry_callback(self, robot_id: str, callback: Callable):
        """
        註冊小車 telemetry 回調

        :param robot_id: 小車 ID
        :param callback: 回調函數，簽名 callback(telemetry: dict) -> None
        """
        self.robot_telemetry_callbacks[robot_id] = callback

    def publish_plan(self, robot_id: str, plan_actions: list, plan_stops: list) -> bool:
        """
        發佈規劃結果給小車

        MQTT 主題: robot/{robot_id}/plan
        """
        topic = f"robot/{robot_id}/plan"
        payload = {
            "robot_id": robot_id,
            "actions": plan_actions,
            "stops": plan_stops,
            "timestamp": datetime.now().isoformat(),
        }
        return self.client.publish(topic, payload)

    def publish_replan_request(self, robot_id: str) -> bool:
        """
        發佈重新規劃請求

        MQTT 主題: robot/{robot_id}/replan-req
        """
        topic = f"robot/{robot_id}/replan-req"
        payload = {
            "robot_id": robot_id,
            "request_time": datetime.now().isoformat(),
        }
        return self.client.publish(topic, payload)

    def simulate_robot_telemetry(self, robot_id: str, node: str):
        """
        （測試用）模擬小車發送位置更新

        用於本地開發測試，不需要真實小車
        """
        if not self.use_mock:
            raise RuntimeError("simulate_robot_telemetry only works with mock client")

        payload = {
            "robot_id": robot_id,
            "node": node,
            "timestamp": datetime.now().isoformat(),
        }
        self.client.simulate_receive("robot/+/telemetry", payload)


# 全局 MQTT 橋接實例
_mqtt_bridge: Optional[MQTTBridge] = None


def get_mqtt_bridge(broker_url: str = "mqtt://localhost:1883", use_mock: bool = True) -> MQTTBridge:
    """取得全局 MQTT 橋接實例"""
    global _mqtt_bridge
    if _mqtt_bridge is None:
        _mqtt_bridge = MQTTBridge(broker_url, use_mock)
    return _mqtt_bridge
