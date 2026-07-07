# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.models.ops_model import OpsCfg, OpsLog, OpsState
from app.schemas.ops_schema import LogPageResponse, OverviewLogStats
from app.services.ops_service import OpsService


FIXED_NOW = datetime(2026, 6, 25, 16, 0, 0)


def fake_settings(**overrides):
    values = {
        "OPS_OFFLINE_TIMEOUT_MINUTES": 3,
        "OPS_CPU_ALARM_THRESHOLD": 1,
        "OPS_MEM_ALARM_THRESHOLD": 0.9,
        "OPS_DISK_ALARM_THRESHOLD": 0.9,
        "OPS_DEFAULT_PAGE_NO": 1,
        "OPS_DEFAULT_PAGE_SIZE": 10,
        "OPS_MAX_PAGE_SIZE": 100,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def fmt_time(value: datetime) -> str:
    return value.strftime("%Y%m%d %H:%M:%S")


def cfg(cfg_type="os", machine_tag="machine1", group_name="algo00x", cfg_key="os", value=None, work_time=None):
    return OpsCfg(
        type=cfg_type,
        machine_tag=machine_tag,
        group_name=group_name,
        cfg_key=cfg_key,
        value=value,
        work_time=work_time,
        status=1,
    )


def state(state_type="os", machine_tag="machine1", state_key="os", value="os", dat=None, update_time="auto"):
    return OpsState(
        date="20260625",
        type=state_type,
        machine_tag=machine_tag,
        state_key=state_key,
        value=value,
        dat=dat,
        update_time=fmt_time(FIXED_NOW) if update_time == "auto" else update_time,
    )


class FakeOpsService(OpsService):
    def __init__(self, cfgs=None, states=None, settings=None, now=None):
        super().__init__(db=None, settings=settings or fake_settings())
        self.cfgs = cfgs or []
        self.states = states or []
        self.now = now or FIXED_NOW

    def _now(self):
        return self.now

    def _get_active_cfgs(self, cfg_type, group=None):
        items = [item for item in self.cfgs if item.type == cfg_type and item.status == 1]
        if group:
            items = [item for item in items if item.group_name == group]
        return items

    def _get_states(self, state_type, date):
        return [item for item in self.states if item.type == state_type and item.date == date]

    def _get_log_stats(self, group, date, only_error=False):
        return OverviewLogStats()


def stale_time(now=FIXED_NOW, minutes=5):
    return fmt_time(now - timedelta(minutes=minutes))


def test_os_normal():
    service = FakeOpsService(
        cfgs=[cfg()],
        states=[state(dat='{"cpu": 0.2, "mem": 0.3, "disk": 0.4}')],
    )

    item = service.get_os_states(date="20260625")[0]

    assert item.status == "normal"
    assert item.cpu_usage == 0.2
    assert item.memory_usage == 0.3
    assert item.disk_usage == 0.4


def test_os_cpu_mem_disk_thresholds():
    base_cfg = cfg()

    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 1, "mem": 0.2, "disk": 0.2}')]).get_os_states(date="20260625")[0].status == "error"
    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 0.2, "mem": 0.9, "disk": 0.2}')]).get_os_states(date="20260625")[0].status == "error"
    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 0.2, "mem": 0.2, "disk": 0.953}')]).get_os_states(date="20260625")[0].status == "error"


def test_os_decimal_metric_values_are_not_scaled_and_disk_threshold_alarms():
    item = FakeOpsService(
        [cfg(machine_tag="lk_cta_2510")],
        [state(machine_tag="lk_cta_2510", dat='{"cpu": 0.001, "mem": 0.088, "disk": 0.908}')],
    ).get_os_states(date="20260625")[0]

    assert item.cpu_usage == 0.001
    assert item.memory_usage == 0.088
    assert item.disk_usage == 0.908
    assert item.status == "error"


def test_os_decimal_metric_values_under_threshold_are_normal():
    item = FakeOpsService(
        [cfg(machine_tag="lk_cta_2510")],
        [state(machine_tag="lk_cta_2510", dat='{"cpu": 0.001, "mem": 0.088, "disk": 0.808}')],
    ).get_os_states(date="20260625")[0]

    assert item.cpu_usage == 0.001
    assert item.memory_usage == 0.088
    assert item.disk_usage == 0.808
    assert item.status == "normal"

def test_os_thresholds_use_settings():
    base_cfg = cfg()

    assert FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.85, "mem": 0.2, "disk": 0.2}')],
        settings=fake_settings(OPS_CPU_ALARM_THRESHOLD=0.8),
    ).get_os_states(date="20260625")[0].status == "error"
    assert FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.85, "mem": 0.2, "disk": 0.2}')],
        settings=fake_settings(OPS_CPU_ALARM_THRESHOLD=0.9),
    ).get_os_states(date="20260625")[0].status == "normal"
    assert FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.2, "mem": 0.75, "disk": 0.2}')],
        settings=fake_settings(OPS_MEM_ALARM_THRESHOLD=0.7),
    ).get_os_states(date="20260625")[0].status == "error"
    assert FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.2, "mem": 0.2, "disk": 0.75}')],
        settings=fake_settings(OPS_DISK_ALARM_THRESHOLD=0.7),
    ).get_os_states(date="20260625")[0].status == "error"


def test_os_missing_empty_bad_and_stale_update_time_are_offline_when_work_time_empty():
    base_cfg = cfg(work_time="")

    assert FakeOpsService([base_cfg], []).get_os_states(date="20260625")[0].status == "offline"
    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 1, "mem": 1, "disk": 1}', update_time=None)]).get_os_states(date="20260625")[0].status == "offline"
    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 1, "mem": 1, "disk": 1}', update_time="bad")]).get_os_states(date="20260625")[0].status == "offline"
    assert FakeOpsService([base_cfg], [state(dat='{"cpu": 1, "mem": 1, "disk": 1}', update_time=stale_time())]).get_os_states(date="20260625")[0].status == "offline"


def test_offline_timeout_uses_settings_with_fixed_now():
    base_cfg = cfg()
    row = state(dat='{"cpu": 0.1, "mem": 0.1, "disk": 0.1}', update_time=stale_time(minutes=5))

    assert FakeOpsService([base_cfg], [row], settings=fake_settings(OPS_OFFLINE_TIMEOUT_MINUTES=3)).get_os_states(date="20260625")[0].status == "offline"
    assert FakeOpsService([base_cfg], [row], settings=fake_settings(OPS_OFFLINE_TIMEOUT_MINUTES=10)).get_os_states(date="20260625")[0].status == "normal"


def test_os_stale_state_is_offline_only_inside_work_time():
    row = state(dat='{"cpu": 0.1, "mem": 0.1, "disk": 0.1}', update_time=stale_time())

    inside = FakeOpsService(
        [cfg(work_time="09:00:00-23:00:00")],
        [row],
    ).get_os_states(date="20260625")[0]
    outside = FakeOpsService(
        [cfg(work_time="09:00:00-15:00:00;21:00:00-23:00:00")],
        [row],
    ).get_os_states(date="20260625")[0]

    assert inside.status == "offline"
    assert inside.cpu_usage == 0.1
    assert inside.memory_usage == 0.1
    assert inside.disk_usage == 0.1
    assert outside.status == "normal"
    assert outside.cpu_usage == 0.1
    assert outside.memory_usage == 0.1
    assert outside.disk_usage == 0.1


def test_os_stale_state_keeps_last_reported_usage_values():
    now = datetime(2026, 7, 6, 15, 5, 0)
    row = state(
        machine_tag="lk_cta_2510",
        dat="{'cpu': 0.002, 'mem': 0.369, 'disk': 0.889}",
        update_time="20260706 14:59:10",
    )

    item = FakeOpsService(
        [cfg(machine_tag="lk_cta_2510", work_time="09:00:00-23:00:00")],
        [row],
        now=now,
    ).get_os_states(date="20260625")[0]

    assert item.machine_tag == "lk_cta_2510"
    assert item.cpu_usage == 0.002
    assert item.memory_usage == 0.369
    assert item.disk_usage == 0.889
    assert item.update_time == "20260706 14:59:10"
    assert item.status == "offline"


def test_os_missing_state_respects_work_time():
    inside = FakeOpsService([cfg(work_time="09:00:00-23:00:00")]).get_os_states(date="20260625")[0]
    outside = FakeOpsService([cfg(work_time="09:00:00-15:00:00;21:00:00-23:00:00")]).get_os_states(date="20260625")[0]

    assert inside.status == "offline"
    assert inside.cpu_usage is None
    assert inside.memory_usage is None
    assert inside.disk_usage is None
    assert outside.status == "normal"
    assert outside.cpu_usage is None
    assert outside.memory_usage is None
    assert outside.disk_usage is None


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
        update_time=stale_time(),
    )
    item = FakeOpsService([process_cfg], [stale_state]).get_process_states(date="20260625")[0]
    assert item.status == "offline"
    assert item.pid == 103833


def test_process_stale_state_is_offline_only_inside_work_time():
    row = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['sys_simnow.yaml']",
        dat="{'pid': 103833}",
        update_time=stale_time(),
    )

    inside = FakeOpsService(
        [cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml", work_time="09:00:00-23:00:00")],
        [row],
    ).get_process_states(date="20260625")[0]
    outside = FakeOpsService(
        [cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml", work_time="09:00:00-15:00:00;21:00:00-23:00:00")],
        [row],
    ).get_process_states(date="20260625")[0]

    assert inside.status == "offline"
    assert inside.pid == 103833
    assert outside.status == "normal"
    assert outside.pid == 103833


def test_process_missing_state_respects_work_time():
    process_cfg_inside = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml", work_time="09:00:00-23:00:00")
    process_cfg_outside = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml", work_time="09:00:00-15:00:00;21:00:00-23:00:00")

    assert FakeOpsService([process_cfg_inside], []).get_process_states(date="20260625")[0].status == "offline"
    assert FakeOpsService([process_cfg_outside], []).get_process_states(date="20260625")[0].status == "normal"


def test_process_state_matches_by_type_key_and_value_containment():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml")
    matching_state = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['sys_simnow.yaml', 'user_simnow_20260605_am.yaml']",
        dat="{'pid': 103833}",
    )
    non_matching_value = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['other.yaml']",
        dat="{'pid': 2}",
    )
    non_matching_type = state(
        state_type="os",
        state_key="./bin/tlBinTradeLite",
        value="['sys_simnow.yaml']",
        dat="{'pid': 1}",
    )

    assert OpsService._find_process_state(process_cfg, [non_matching_type]) is None
    item = FakeOpsService([process_cfg], [non_matching_value, matching_state]).get_process_states(date="20260625")[0]

    assert item.status == "normal"
    assert item.pid == 103833


def test_process_empty_cfg_value_does_not_filter_by_state_value():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="")
    row = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['other.yaml']",
        dat="{'pid': 103833}",
    )

    item = FakeOpsService([process_cfg], [row]).get_process_states(date="20260625")[0]

    assert item.status == "normal"
    assert item.pid == 103833


def test_process_overview_counts_stale_alarm_only_inside_work_time():
    row = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['sys_simnow.yaml']",
        dat="{'pid': 103833}",
        update_time=stale_time(),
    )
    inside_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml", work_time="09:00:00-23:00:00")
    outside_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml", work_time="09:00:00-15:00:00;21:00:00-23:00:00")

    inside = FakeOpsService([inside_cfg], [row]).get_overview(date="20260625")
    outside = FakeOpsService([outside_cfg], [row]).get_overview(date="20260625")

    assert inside.process.total == 1
    assert inside.process.alarm_count == 1
    assert inside.process.abnormal_count == 1
    assert outside.process.total == 1
    assert outside.process.alarm_count == 0
    assert outside.process.abnormal_count == 0


def test_overview_counts_missing_state_and_decimal_disk_alarm():
    service = FakeOpsService(
        cfgs=[
            cfg(machine_tag="missing", work_time="09:00:00-23:00:00"),
            cfg(machine_tag="disk-alarm", work_time="09:00:00-23:00:00"),
        ],
        states=[
            state(machine_tag="disk-alarm", dat='{"cpu": 0.001, "mem": 0.088, "disk": 0.908}'),
        ],
    )

    overview = service.get_overview(date="20260625")

    assert overview.os.total == 2
    assert overview.os.alarm_count == 2
    assert overview.os.abnormal_count == 2

def test_group_and_only_error_filters():
    service = FakeOpsService(
        cfgs=[
            cfg(machine_tag="normal", group_name="algo00x"),
            cfg(machine_tag="error", group_name="op"),
        ],
        states=[
            state(machine_tag="normal", dat='{"cpu": 0.1, "mem": 0.1, "disk": 0.1}'),
            state(machine_tag="error", dat='{"cpu": 0.1, "mem": 0.95, "disk": 0.1}'),
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
    service = OpsService(FakeLevelDb([("error",), ("warn",), ("info",)]), settings=fake_settings())
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

