# -*- coding: utf-8 -*-
"""P0 工程化端点测试：/health 与统一校验错误结构。"""
from fastapi.testclient import TestClient


def test_health_returns_ok_when_database_available():
    from app.main import app

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"


def test_validation_error_returns_unified_envelope():
    from app.main import app

    response = TestClient(app).post(
        "/api_omms/monitor/overview/os/list", json={"gropy": "op"}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 422
    assert body["msg"] == "request validation failed"
    assert body["errors"] and body["errors"][0]["field"] == "body.gropy"
