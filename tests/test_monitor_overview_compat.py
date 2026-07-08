# -*- coding: utf-8 -*-
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.controllers.monitor_overview_controller import (
    MonitorOverviewController,
    get_monitor_overview_controller,
)
from app.schemas.monitor_overview_schema import (
    MonitorOverviewLogListRequest,
    MonitorOverviewOsListRequest,
    MonitorOverviewProcessListRequest,
)
from app.schemas.ops_schema import (
    LogItem,
    LogPageResponse,
    OsStateItem,
    OverviewLogStats,
    OverviewOsStats,
    OverviewProcessStats,
    OverviewResponse,
    ProcessStateItem,
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
        self.process_state_calls = []
        self.log_calls = []

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
                cpu_usage=0.65,
                memory_usage=0.86,
                disk_usage=0.72,
                update_time="2026-07-02 16:20:30",
                status="normal",
                message="ok",
            ),
            OsStateItem(
                machine_tag="machine-offline",
                group="op",
                cpu_usage=0.1,
                memory_usage=0.2,
                disk_usage=0.3,
                update_time="2026-07-02 16:10:30",
                status="offline",
                message="offline",
            ),
        ]
        if group:
            return [item for item in items if item.group == group]
        return items

    def get_process_states(self, group=None):
        self.process_state_calls.append({"group": group})
        items = [
            ProcessStateItem(
                machine_tag="machine-b",
                group="algo00x",
                process_name="zProcess",
                pid=141976,
                cpu=0.116,
                memory=2097.57,
                update_time="20260706 23:59:54",
                status="normal",
                message="normal",
            ),
            ProcessStateItem(
                machine_tag="machine-c",
                group="op",
                process_name="aProcess",
                pid=2,
                cpu=0.2,
                memory=200.5,
                update_time="20260706 23:50:00",
                status="offline",
                message="offline",
            ),
            ProcessStateItem(
                machine_tag="machine-a",
                group="op",
                process_name="bProcess",
                pid=None,
                cpu=None,
                memory=None,
                update_time=None,
                status="unknown",
                message="parse failed",
            ),
        ]
        if group:
            return [item for item in items if item.group == group]
        return items



    def get_logs(
        self,
        group=None,
        machine_tag=None,
        level=None,
        date=None,
        page=1,
        page_size=20,
        only_error=False,
        sort_by="",
        sort_order="",
    ):
        self.log_calls.append(
            {
                "group": group,
                "machine_tag": machine_tag,
                "level": level,
                "date": date,
                "page": page,
                "page_size": page_size,
                "only_error": only_error,
                "sort_by": sort_by,
                "sort_order": sort_order,
            }
        )
        items = [
            LogItem(
                log_id=3,
                date="20260708",
                machine_tag="machine-b",
                log_name="trade",
                level="ERROR",
                log="error log",
                update_time="20260708 08:50:03",
            ),
            LogItem(
                log_id=2,
                date="20260708",
                machine_tag="machine-a",
                log_name="trade",
                level="warn",
                log="warn log",
                update_time="20260708 08:50:02",
            ),
            LogItem(
                log_id=1,
                date="20260708",
                machine_tag="machine-a",
                log_name="trade",
                level="info",
                log="info log",
                update_time="20260708 08:50:01",
            ),
        ]
        start = (page - 1) * page_size
        end = start + page_size
        return LogPageResponse(items=items[start:end], total=len(items), page=page, page_size=page_size)

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
                "cpu_usage": 0.65,
                "mem_usage": 0.86,
                "disk_usage": 0.72,
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


def test_overview_process_list_uses_defaults_and_returns_page_shape():
    service = FakeOverviewOpsService()
    service.settings = fake_settings(OPS_DEFAULT_PAGE_NO=2, OPS_DEFAULT_PAGE_SIZE=1, OPS_MAX_PAGE_SIZE=50)
    controller = MonitorOverviewController(service)

    result = controller.get_process_list(MonitorOverviewProcessListRequest())

    assert result.model_dump() == {
        "page_no": 2,
        "page_size": 1,
        "total": 3,
        "details": [
            {
                "machine_tag": "machine-a",
                "process_name": "bProcess",
                "pid": None,
                "cpu": None,
                "mem": None,
                "update_time": None,
                "is_offline": 0,
                "is_alarm": 1,
            }
        ],
    }
    assert service.process_state_calls == [{"group": None}]


def test_overview_process_list_supports_group_and_status_flags():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_process_list(MonitorOverviewProcessListRequest(group="op", page_no=1, page_size=10))

    assert result.total == 2
    assert [item.machine_tag for item in result.details] == ["machine-c", "machine-a"]
    assert result.details[0].process_name == "aProcess"
    assert result.details[0].is_offline == 1
    assert result.details[0].is_alarm == 1
    assert result.details[1].is_offline == 0
    assert result.details[1].is_alarm == 1
    assert service.process_state_calls == [{"group": "op"}]


def test_overview_process_list_maps_raw_pid_cpu_mem_values():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_process_list(
        MonitorOverviewProcessListRequest(sort_by="machine_tag", sort_order="asc", page_no=1, page_size=10)
    )

    normal = result.details[1]
    assert normal.machine_tag == "machine-b"
    assert normal.process_name == "zProcess"
    assert normal.pid == 141976
    assert normal.cpu == 0.116
    assert normal.mem == 2097.57
    assert normal.is_offline == 0
    assert normal.is_alarm == 0


def test_overview_process_list_default_sort_puts_alarm_and_offline_first():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_process_list(MonitorOverviewProcessListRequest(page_no=1, page_size=10))

    assert [item.machine_tag for item in result.details] == ["machine-c", "machine-a", "machine-b"]



def test_overview_log_list_uses_defaults_and_returns_page_shape():
    service = FakeOverviewOpsService()
    service.settings = fake_settings(OPS_DEFAULT_PAGE_NO=1, OPS_DEFAULT_PAGE_SIZE=2, OPS_MAX_PAGE_SIZE=50)
    controller = MonitorOverviewController(service)

    result = controller.get_log_list(MonitorOverviewLogListRequest())

    assert result.model_dump() == {
        "page_no": 1,
        "page_size": 2,
        "total": 3,
        "details": [
            {
                "log_id": 3,
                "date": "20260708",
                "machine_tag": "machine-b",
                "log_name": "trade",
                "level": "error",
                "log": "error log",
                "update_time": "20260708 08:50:03",
                "is_alarm": 1,
            },
            {
                "log_id": 2,
                "date": "20260708",
                "machine_tag": "machine-a",
                "log_name": "trade",
                "level": "warn",
                "log": "warn log",
                "update_time": "20260708 08:50:02",
                "is_alarm": 1,
            },
        ],
    }
    assert service.log_calls == [
        {
            "group": None,
            "machine_tag": None,
            "level": None,
            "date": None,
            "page": 1,
            "page_size": 2,
            "only_error": False,
            "sort_by": "",
            "sort_order": "",
        }
    ]


def test_overview_log_list_passes_filters_sort_and_pagination():
    service = FakeOverviewOpsService()
    controller = MonitorOverviewController(service)

    result = controller.get_log_list(
        MonitorOverviewLogListRequest(
            group="op",
            only_error=1,
            level="ERROR",
            date="20260708",
            page_no=2,
            page_size=1,
            sort_by="machine_tag",
            sort_order="asc",
        )
    )

    assert result.page_no == 2
    assert result.page_size == 1
    assert result.total == 3
    assert result.details[0].level == "warn"
    assert result.details[0].is_alarm == 1
    assert service.log_calls == [
        {
            "group": "op",
            "machine_tag": None,
            "level": "error",
            "date": "20260708",
            "page": 2,
            "page_size": 1,
            "only_error": True,
            "sort_by": "machine_tag",
            "sort_order": "asc",
        }
    ]


def test_overview_log_item_marks_info_as_not_alarm():
    item = MonitorOverviewController._to_monitor_log_item(
        LogItem(
            log_id=1,
            date="20260708",
            machine_tag="machine-a",
            log_name="trade",
            level="info",
            log="info log",
            update_time="20260708 08:50:01",
        )
    )

    assert item.is_alarm == 0
    assert item.level == "info"

def test_monitor_overview_routes_are_registered_without_legacy_ops_routes():
    from app.main import app

    paths = {route.path for route in app.routes}

    assert "/api_omms/monitor/overview/total" in paths
    assert "/api_omms/monitor/overview/os/list" in paths
    assert "/api_omms/monitor/overview/process/list" in paths
    assert "/api_omms/monitor/overview/log/list" in paths
    assert not any(path.startswith("/api/ops") for path in paths)


def test_monitor_overview_openapi_matches_current_routes():
    from app.main import app

    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api_omms/monitor/overview/total" in paths
    assert "get" in paths["/api_omms/monitor/overview/total"]
    assert "/api_omms/monitor/overview/os/list" in paths
    assert "post" in paths["/api_omms/monitor/overview/os/list"]
    assert "/api_omms/monitor/overview/process/list" in paths
    assert "post" in paths["/api_omms/monitor/overview/process/list"]
    assert "/api_omms/monitor/overview/log/list" in paths
    assert "post" in paths["/api_omms/monitor/overview/log/list"]
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


def test_monitor_overview_process_list_route_accepts_empty_body_and_declares_utf8_charset():
    from app.main import app

    class FakeController:
        def get_process_list(self, request=None):
            return {"page_no": 1, "page_size": 10, "total": 0, "details": []}

    app.dependency_overrides[get_monitor_overview_controller] = lambda: FakeController()
    try:
        response = TestClient(app).post("/api_omms/monitor/overview/process/list")
    finally:
        app.dependency_overrides.pop(get_monitor_overview_controller, None)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.json()["data"] == {"page_no": 1, "page_size": 10, "total": 0, "details": []}


def test_monitor_overview_log_list_route_accepts_empty_body_and_declares_utf8_charset():
    from app.main import app

    class FakeController:
        def get_log_list(self, request=None):
            return {"page_no": 1, "page_size": 10, "total": 0, "details": []}

    app.dependency_overrides[get_monitor_overview_controller] = lambda: FakeController()
    try:
        response = TestClient(app).post("/api_omms/monitor/overview/log/list")
    finally:
        app.dependency_overrides.pop(get_monitor_overview_controller, None)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.json()["data"] == {"page_no": 1, "page_size": 10, "total": 0, "details": []}

def test_monitor_overview_os_list_rejects_gropy_typo():
    from app.main import app

    response = TestClient(app).post("/api_omms/monitor/overview/os/list", json={"gropy": "op"})

    assert response.status_code == 422


def test_monitor_overview_process_list_rejects_gropy_typo():
    from app.main import app

    response = TestClient(app).post("/api_omms/monitor/overview/process/list", json={"gropy": "op"})

    assert response.status_code == 422


def test_monitor_overview_log_list_rejects_gropy_typo():
    from app.main import app

    response = TestClient(app).post("/api_omms/monitor/overview/log/list", json={"gropy": "op"})

    assert response.status_code == 422
