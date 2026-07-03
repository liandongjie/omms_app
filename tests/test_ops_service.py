# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from app.models.ops_model import OpsCfg, OpsLog, OpsState
from app.schemas.ops_schema import LogPageResponse
from app.services.ops_service import OpsService


def fmt_time(value: datetime) -> str:
    return value.strftime("%Y%m%d %H:%M:%S")


def cfg(cfg_type="os", machine_tag="machine1", group_name="algo00x", cfg_key="os", value=None):
    return OpsCfg(
        type=cfg_type,
        machine_tag=machine_tag,
        group_name=group_name,
        cfg_key=cfg_key,
        value=value,
        status=1,
    )


def state(state_type="os", machine_tag="machine1", state_key="os", value="os", dat=None, update_time=None):
    return OpsState(
        date="20260625",
        type=state_type,
        machine_tag=machine_tag,
        state_key=state_key,
        value=value,
        dat=dat,
        update_time=update_time or fmt_time(datetime.now()),
    )


class FakeOpsService(OpsService):
    def __init__(self, cfgs=None, states=None):
        super().__init__(db=None)
        self.cfgs = cfgs or []
        self.states = states or []

    def _get_active_cfgs(self, cfg_type, group=None):
        items = [item for item in self.cfgs if item.type == cfg_type and item.status == 1]
        if group:
            items = [item for item in items if item.group_name == group]
        return items

    def _get_states(self, state_type, date):
        return [item for item in self.states if item.type == state_type and item.date == date]


def test_os_normal():
    service = FakeOpsService(
        cfgs=[cfg()],
        states=[state(dat='{"cpu": 0.2, "mem": 0.3, "disk": 0.4}')],
    )

    item = service.get_os_states(date="20260625")[0]

    assert item.status == "normal"
    assert item.cpu_usage == 20
    assert item.memory_usage == 30
    assert item.disk_usage == 40


def test_os_cpu_mem_disk_thresholds():
    base_cfg = cfg()

    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 100, "mem": 20, "disk": 20}')]).get_os_states(date="20260625")[0].status == "error"
    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 20, "mem": 90, "disk": 20}')]).get_os_states(date="20260625")[0].status == "error"
    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 20, "mem": 20, "disk": 0.953}')]).get_os_states(date="20260625")[0].status == "error"


def test_os_missing_state_and_stale_state():
    item = FakeOpsService([cfg()], []).get_os_states(date="20260625")[0]
    assert item.status == "offline"
    assert item.message == "未找到最新状态"

    stale_time = fmt_time(datetime.now() - timedelta(minutes=5))
    item = FakeOpsService([cfg()], [state(dat='{"cpu": 1, "mem": 1, "disk": 1}', update_time=stale_time)]).get_os_states(date="20260625")[0]
    assert item.status == "offline"


def test_os_parse_failure_returns_unknown_instead_of_raising():
    item = FakeOpsService([cfg()], [state(dat="{broken")]).get_os_states(date="20260625")[0]
    assert item.status == "unknown"


def test_process_normal_missing_and_stale():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml")
    fresh_state = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['sys_simnow.yaml']",
        dat="{'pid': 103833, 'cpu': 0.109, 'mem': 2100.254}",
    )
    item = FakeOpsService([process_cfg], [fresh_state]).get_process_states(date="20260625")[0]
    assert item.status == "normal"
    assert item.pid == 103833

    item = FakeOpsService([process_cfg], []).get_process_states(date="20260625")[0]
    assert item.status == "offline"

    stale_state = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['sys_simnow.yaml']",
        dat="{'pid': 103833}",
        update_time=fmt_time(datetime.now() - timedelta(minutes=5)),
    )
    item = FakeOpsService([process_cfg], [stale_state]).get_process_states(date="20260625")[0]
    assert item.status == "offline"


def test_group_and_only_error_filters():
    service = FakeOpsService(
        cfgs=[
            cfg(machine_tag="normal", group_name="algo00x"),
            cfg(machine_tag="error", group_name="op"),
        ],
        states=[
            state(machine_tag="normal", dat='{"cpu": 10, "mem": 10, "disk": 10}'),
            state(machine_tag="error", dat='{"cpu": 10, "mem": 95, "disk": 10}'),
        ],
    )

    assert [item.machine_tag for item in service.get_os_states(group="op", date="20260625")] == ["error"]
    assert [item.machine_tag for item in service.get_os_states(only_error=True, date="20260625")] == ["error"]


class FakeLevelQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def all(self):
        return self.rows


class FakeLevelDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *args):
        return FakeLevelQuery(self.rows)


def test_log_error_warn_info_stats():
    service = OpsService(FakeLevelDb([("error",), ("warn",), ("info",)]))
    stats = service._get_log_stats(group=None, date="20260625")

    assert stats.total == 3
    assert stats.error_count == 1
    assert stats.warn_count == 1
    assert stats.alarm_count == 2


def test_alarm_list_includes_warn_and_error_logs_only():
    class AlarmService(FakeOpsService):
        def get_logs(self, **kwargs):
            return LogPageResponse(
                total=3,
                page=1,
                page_size=200,
                items=[
                    OpsService._build_log_item(OpsLog(log_id=1, level="error", log="bad", machine_tag="m1", log_name="tradeLite"), "algo00x"),
                    OpsService._build_log_item(OpsLog(log_id=2, level="warn", log="warn", machine_tag="m1", log_name="tradeLite"), "algo00x"),
                    OpsService._build_log_item(OpsLog(log_id=3, level="info", log="ok", machine_tag="m1", log_name="tradeLite"), "algo00x"),
                ],
            )

    alarms = AlarmService().get_alarms(date="20260625")

    assert [alarm.level for alarm in alarms] == ["error", "warning"]


def test_empty_data_returns_empty_lists():
    service = FakeOpsService()
    assert service.get_os_states(date="20260625") == []
    assert service.get_process_states(date="20260625") == []
