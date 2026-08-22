# -*- coding: utf-8 -*-
"""WebSocket 实时推送端点测试。"""
from fastapi.testclient import TestClient


def test_monitor_websocket_is_registered_in_routes():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/ws/monitor" in paths


def test_monitor_websocket_hello_and_pong():
    from app.main import app

    with TestClient(app) as client:
        with client.websocket_connect("/ws/monitor") as websocket:
            hello = websocket.receive_json()
            assert hello["event"] == "hello"
            websocket.send_text("ping")
            pong = websocket.receive_json()
            assert pong["event"] == "pong"
