# -*- coding: utf-8 -*-
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.controllers.monitor_overview_controller import (
    MonitorOverviewController,
    get_monitor_overview_controller,
)
from app.schemas.monitor_overview_schema import MonitorOverviewOsListRequest
from app.schemas.ops_schema import (
    OsStateItem,
    OverviewLogStats,
    OverviewOsStats,
    OverviewProcessStats,
    OverviewResponse,
)


def fake_settings(**overrides):
    values = {
        "OPS_DEFAULT_PAGE_NO": 1,
        "OPS_DEFAULT_PAGE_SIZE": 10,
        "OPS_MAX_PAGE_SIZE": 100,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeOverviewOpsService:
    def __init__(self):
        self.settings = fake_settings()
        self.overview_calls = []
        self.os_state_calls = []

    def get_overview(self):
        self.overview_calls.append({})
        return OverviewResponse(
            os=OverviewOsStats(total=10, alarm_count=2),
            process=OverviewProcessStats(total=30, alarm_count=5),
            log=OverviewLogStats(total=120, alarm_count=15, error_count=2),
        )

    def get_os_states(self, group=None):
        self.os_state_calls.append({"group": group})
        items = [
            OsStateItem(
                machine_tag="machine-normal",
                group="algo00x",
                cpu_usage=65,
                memory_usage=86,
                disk_usage=72,
                update_time="2026-07-02 16:20:30",
                status="normal",
                message="ok",
            ),
            OsStateItem(
                machine_tag="machine-offline",
                group="op",
                cpu_usage=10,
                memory_usage=20,
                disk_usage=30,
                update_time="2026-07-02 16:10:30",
                status="offline",
                message="offline",
            ),
        ]
        if group:
            return [item for item in items if item.group == group]
        return items


def test_overview_total_matches_current_shape():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_total()

    assert result.model_dump() == {
        "os": {"total": 10, "alarm": 2, "error": 2},
        "process": {"total": 30, "alarm": 5, "error": 5},
        "log": {"total": 120, "alarm": 15, "error": 2},
    }
    assert service.overview_calls == [{}]


def test_overview_os_list_uses_defaults_and_returns_page_shape():
    service = FakeOverviewOpsService()
    service.settings = fake_settings(OPS_DEFAULT_PAGE_NO=2, OPS_DEFAULT_PAGE_SIZE=1, OPS_MAX_PAGE_SIZE=50)
    controller = MonitorOverviewController(service)

    result = controller.get_os_list(MonitorOverviewOsListRequest())

    assert result.model_dump() == {
        "page_no": 2,
        "page_size": 1,
        "total": 2,
        "details": [
            {
                "machine_tag": "machine-normal",
                "cpu_usage": 65.0,
                "mem_usage": 86.0,
                "disk_usage": 72.0,
                "update_time": "2026-07-02 16:20:30",
                "is_offline": 0,
                "is_alarm": 0,
            }
        ],
    }
    assert service.os_state_calls == [{"group": None}]


def test_overview_os_list_supports_group_and_pagination():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_os_list(MonitorOverviewOsListRequest(group="op", page_no=1, page_size=10))

    assert result.total == 1
    assert result.details[0].machine_tag == "machine-offline"
    assert result.details[0].is_offline == 1
    assert result.details[0].is_alarm == 1
    assert service.os_state_calls == [{"group": "op"}]


def test_overview_os_list_clamps_page_size_to_config():
    service = FakeOverviewOpsService()
    service.settings = fake_settings(OPS_DEFAULT_PAGE_NO=1, OPS_DEFAULT_PAGE_SIZE=10, OPS_MAX_PAGE_SIZE=1)
    controller = MonitorOverviewController(service)

    result = controller.get_os_list(MonitorOverviewOsListRequest(page_size=999))

    assert result.page_size == 1
    assert len(result.details) == 1


def test_monitor_overview_routes_are_registered_without_legacy_ops_routes():
    from app.main import app

    paths = {route.path for route in app.routes}

    assert "/api_omms/monitor/overview/total" in paths
    assert "/api_omms/monitor/overview/os/list" in paths
    assert not any(path.startswith("/api/ops") for path in paths)


def test_monitor_overview_openapi_matches_current_routes():
    from app.main import app

    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api_omms/monitor/overview/total" in paths
    assert "get" in paths["/api_omms/monitor/overview/total"]
    assert "/api_omms/monitor/overview/os/list" in paths
    assert "post" in paths["/api_omms/monitor/overview/os/list"]
    assert not any(path.startswith("/api/ops") for path in paths)


def test_monitor_overview_total_route_has_no_required_params():
    from app.main import app

    class FakeController:
        def get_total(self):
            return {
                "os": {"total": 10, "alarm": 2, "error": 2},
                "process": {"total": 30, "alarm": 5, "error": 5},
                "log": {"total": 120, "alarm": 15, "error": 2},
            }

    app.dependency_overrides[get_monitor_overview_controller] = lambda: FakeController()
    try:
        response = TestClient(app).get("/api_omms/monitor/overview/total")
    finally:
        app.dependency_overrides.pop(get_monitor_overview_controller, None)

    assert response.status_code == 200
    assert response.json()["data"]["os"] == {"total": 10, "alarm": 2, "error": 2}


def test_monitor_overview_os_list_route_accepts_empty_body_and_declares_utf8_charset():
    from app.main import app

    class FakeController:
        def get_os_list(self, request=None):
            return {"page_no": 1, "page_size": 10, "total": 0, "details": []}

    app.dependency_overrides[get_monitor_overview_controller] = lambda: FakeController()
    try:
        response = TestClient(app).post("/api_omms/monitor/overview/os/list")
    finally:
        app.dependency_overrides.pop(get_monitor_overview_controller, None)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.json()["data"] == {"page_no": 1, "page_size": 10, "total": 0, "details": []}


def test_monitor_overview_os_list_rejects_gropy_typo():
    from app.main import app

    response = TestClient(app).post("/api_omms/monitor/overview/os/list", json={"gropy": "op"})

    assert response.status_code == 422
