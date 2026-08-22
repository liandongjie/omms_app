# -*- coding: utf-8 -*-
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.controllers.monitor_overview_controller import get_monitor_overview_controller
from app.main import app


def _request_total(controller):
    app.dependency_overrides[get_monitor_overview_controller] = lambda: controller
    try:
        return TestClient(app, raise_server_exceptions=False).get(
            "/api_omms/monitor/overview/total"
        )
    finally:
        app.dependency_overrides.pop(get_monitor_overview_controller, None)


def test_runtime_error_returns_sanitized_500_envelope():
    class FailingController:
        def get_total(self):
            raise RuntimeError("boom-secret")

    response = _request_total(FailingController())

    assert response.status_code == 500
    assert response.json() == {
        "code": 500,
        "msg": "internal server error",
        "errors": None,
    }
    assert "boom-secret" not in response.text


def test_http_500_detail_is_not_exposed():
    class FailingController:
        def get_total(self):
            raise HTTPException(status_code=500, detail="boom-http-secret")

    response = _request_total(FailingController())

    assert response.status_code == 500
    assert response.json()["msg"] == "internal server error"
    assert "boom-http-secret" not in response.text


def test_validation_error_returns_unified_422_envelope():
    response = TestClient(app).post(
        "/api_omms/monitor/overview/os/list", json={"gropy": "op"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 422
    assert body["msg"] == "request validation failed"
    assert body["errors"] and body["errors"][0]["field"] == "body.gropy"


def test_normal_route_keeps_existing_response_contract():
    class SuccessfulController:
        def get_total(self):
            return {
                "os": {"total": 1, "alarm": 0, "error": 0},
                "process": {"total": 2, "alarm": 1, "error": 1},
                "log": {"total": 3, "alarm": 2, "error": 1},
            }

    response = _request_total(SuccessfulController())

    assert response.status_code == 200
    assert response.json() == {
        "code": 200,
        "msg": "success",
        "data": {
            "os": {"total": 1, "alarm": 0, "error": 0},
            "process": {"total": 2, "alarm": 1, "error": 1},
            "log": {"total": 3, "alarm": 2, "error": 1},
        },
    }
