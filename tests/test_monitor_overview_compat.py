# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient
from app.controllers.monitor_overview_controller import (
    MonitorOverviewController,
    get_monitor_overview_controller,
)
from app.schemas.ops_schema import (
    OsStateItem,
    OverviewLogStats,
    OverviewOsStats,
    OverviewProcessStats,
    OverviewResponse,
)


class FakeOverviewOpsService:
    def __init__(self):
        self.overview_calls = []
        self.os_state_calls = []

    def get_overview(self, group=None, only_error=False):
        self.overview_calls.append({"group": group, "only_error": only_error})
        return OverviewResponse(
            os=OverviewOsStats(total=10, alarm_count=2),
            process=OverviewProcessStats(total=30, alarm_count=5),
            log=OverviewLogStats(total=120, alarm_count=15),
        )

    def get_os_states(self, group=None, only_error=False):
        self.os_state_calls.append({"group": group, "only_error": only_error})
        items = [
            OsStateItem(
                machine_tag="machine-normal",
                cpu_usage=65,
                memory_usage=86,
                disk_usage=72,
                update_time="2026-07-02 16:20:30",
                status="normal",
                message="ok",
            ),
            OsStateItem(
                machine_tag="machine-offline",
                cpu_usage=10,
                memory_usage=20,
                disk_usage=30,
                update_time="2026-07-02 16:10:30",
                status="offline",
                message="offline",
            ),
        ]
        if only_error:
            return [item for item in items if item.status != "normal"]
        return items


def test_overview_total_matches_mentor_shape():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_total(group="all", only_error=0)

    assert result.model_dump() == {
        "os": {"total": 10, "alarm": 2},
        "process": {"total": 30, "alarm": 5},
        "log": {"total": 120, "alarm": 15},
    }
    assert service.overview_calls == [{"group": None, "only_error": False}]


def test_overview_os_list_matches_mentor_shape_and_filters_errors():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_os_list(group="op", only_error=1)

    assert [item.model_dump() for item in result] == [
        {
            "machine_tag": "machine-offline",
            "cpu_usage": 10.0,
            "mem_usage": 20.0,
            "disk_usage": 30.0,
            "update_time": "2026-07-02 16:10:30",
            "is_offline": 1,
            "is_alarm": 1,
        }
    ]
    assert service.os_state_calls == [{"group": "op", "only_error": True}]


def test_monitor_overview_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}

    assert "/api_omms/monitor/overview/total" in paths
    assert "/api_omms/monitor/overview/os/list" in paths
    assert "/api/monitor/overview/os/list" not in paths


def test_monitor_overview_json_response_declares_utf8_charset():
    from app.main import app

    class FakeController:
        def get_os_list(self, group="all", only_error=0):
            return []

    app.dependency_overrides[get_monitor_overview_controller] = lambda: FakeController()
    try:
        response = TestClient(app).get("/api_omms/monitor/overview/os/list")
    finally:
        app.dependency_overrides.pop(get_monitor_overview_controller, None)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"

def test_overview_group_uses_real_cfg_group_value():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    controller.get_total(group="algo00x", only_error=0)

    assert service.overview_calls == [{"group": "algo00x", "only_error": False}]
