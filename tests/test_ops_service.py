# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
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


def test_os_disk_home_uses_raw_value_and_disk_threshold():
    item = FakeOpsService(
        [cfg()],
        [state(dat='{"cpu": 0.2, "mem": 0.2, "disk": 0.3, "disk_home": 0.7}')],
        settings=fake_settings(OPS_DISK_ALARM_THRESHOLD=0.7),
    ).get_os_states(date="20260625")[0]

    assert item.disk_usage == 0.3
    assert item.disk_home_usage == 0.7
    assert item.disk_alarm == 0
    assert item.disk_home_alarm == 1
    assert item.status == "error"


def test_os_disk_and_disk_home_alarms_are_independent():
    disk_alarm = FakeOpsService(
        [cfg()],
        [state(dat='{"cpu": 0.2, "mem": 0.2, "disk": 0.8, "disk_home": 0.4}')],
        settings=fake_settings(OPS_DISK_ALARM_THRESHOLD=0.7),
    ).get_os_states(date="20260625")[0]
    disk_home_alarm = FakeOpsService(
        [cfg()],
        [state(dat='{"cpu": 0.2, "mem": 0.2, "disk": 0.4, "disk_home": 0.8}')],
        settings=fake_settings(OPS_DISK_ALARM_THRESHOLD=0.7),
    ).get_os_states(date="20260625")[0]

    assert (disk_alarm.disk_alarm, disk_alarm.disk_home_alarm) == (1, 0)
    assert (disk_home_alarm.disk_alarm, disk_home_alarm.disk_home_alarm) == (0, 1)


def test_os_missing_invalid_or_negative_disk_home_does_not_affect_required_metrics_status():
    missing = FakeOpsService(
        [cfg()],
        [state(dat='{"cpu": 0.2, "mem": 0.3, "disk": 0.4}')],
    ).get_os_states(date="20260625")[0]
    invalid = FakeOpsService(
        [cfg()],
        [state(dat='{"cpu": 0.2, "mem": 0.3, "disk": 0.4, "disk_home": "bad"}')],
    ).get_os_states(date="20260625")[0]
    negative = FakeOpsService(
        [cfg()],
        [state(dat='{"cpu": 0.2, "mem": 0.3, "disk": 0.4, "disk_home": -1}')],
    ).get_os_states(date="20260625")[0]

    for item in (missing, invalid, negative):
        assert item.disk_usage == 0.4
        assert item.disk_home_usage is None
        assert item.disk_home_alarm == 0
        assert item.status == "normal"


def test_os_offline_status_takes_priority_over_disk_home_alarm():
    item = FakeOpsService(
        [cfg(work_time="")],
        [state(dat='{"cpu": 0.2, "mem": 0.3, "disk": 0.4, "disk_home": 1}', update_time=stale_time())],
    ).get_os_states(date="20260625")[0]

    assert item.disk_home_alarm == 1
    assert item.status == "offline"

def test_os_thresholds_use_settings():
    base_cfg = cfg()

    cpu_alarm = FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.85, "mem": 0.2, "disk": 0.2}')],
        settings=fake_settings(OPS_CPU_ALARM_THRESHOLD=0.8),
    ).get_os_states(date="20260625")[0]
    assert cpu_alarm.status == "error"
    assert cpu_alarm.cpu_alarm == 1
    assert cpu_alarm.mem_alarm == 0
    assert cpu_alarm.disk_alarm == 0

    cpu_normal = FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.85, "mem": 0.2, "disk": 0.2}')],
        settings=fake_settings(OPS_CPU_ALARM_THRESHOLD=0.9),
    ).get_os_states(date="20260625")[0]
    assert cpu_normal.status == "normal"
    assert cpu_normal.cpu_alarm == 0
    assert cpu_normal.mem_alarm == 0
    assert cpu_normal.disk_alarm == 0

    mem_alarm = FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.2, "mem": 0.75, "disk": 0.2}')],
        settings=fake_settings(OPS_MEM_ALARM_THRESHOLD=0.7),
    ).get_os_states(date="20260625")[0]
    assert mem_alarm.status == "error"
    assert mem_alarm.cpu_alarm == 0
    assert mem_alarm.mem_alarm == 1
    assert mem_alarm.disk_alarm == 0

    disk_alarm = FakeOpsService(
        [base_cfg],
        [state(dat='{"cpu": 0.2, "mem": 0.2, "disk": 0.75}')],
        settings=fake_settings(OPS_DISK_ALARM_THRESHOLD=0.7),
    ).get_os_states(date="20260625")[0]
    assert disk_alarm.status == "error"
    assert disk_alarm.cpu_alarm == 0
    assert disk_alarm.mem_alarm == 0
    assert disk_alarm.disk_alarm == 1


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
    assert item.cpu == 0.109
    assert item.memory == 2100.254

    item = FakeOpsService([process_cfg], []).get_process_states(date="20260625")[0]
    assert item.status == "offline"
    assert item.pid is None
    assert item.cpu is None
    assert item.memory is None

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



def test_process_memory_field_can_use_memory_alias():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="sys_simnow.yaml")
    row = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="['sys_simnow.yaml']",
        dat="{'pid': 103833, 'cpu': 0.116, 'memory': 2097.57}",
    )

    item = FakeOpsService([process_cfg], [row]).get_process_states(date="20260625")[0]

    assert item.pid == 103833
    assert item.cpu == 0.116
    assert item.memory == 2097.57


def test_process_args_use_state_value_even_when_dat_args_exists():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="cfg.yaml")
    row = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="cfg.yaml state.yaml",
        dat="{'pid': 103833, 'cpu': 0.116, 'mem': 2097.57, 'args': ['--env', 'prod']}",
    )

    item = FakeOpsService([process_cfg], [row]).get_process_states(date="20260625")[0]

    assert item.args == "cfg.yaml state.yaml"
    assert item.pid == 103833
    assert item.cpu == 0.116
    assert item.memory == 2097.57
    assert item.status == "normal"
    assert item.extra is None


def test_process_extra_uses_dat_fields_except_fixed_columns():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="cfg.yaml")
    row = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="cfg.yaml state.yaml",
        dat=(
            "{'pid': 103833, 'cpu': 0.116, 'mem': 2097.57, 'memory': 2098, "
            "'args': ['--env', 'prod'], 'pname': 'tlBinTradeLite', "
            "'process_name': 'ignoredName', 'drawdown': 0.12, "
            "'order_count': 7, 'status_detail': 'hedging'}"
        ),
    )

    item = FakeOpsService([process_cfg], [row]).get_process_states(date="20260625")[0]

    assert item.args == "cfg.yaml state.yaml"
    assert item.pid == 103833
    assert item.cpu == 0.116
    assert item.memory == 2097.57
    assert item.extra == {
        "drawdown": 0.12,
        "order_count": 7,
        "status_detail": "hedging",
    }


def test_process_extra_is_none_when_dat_empty_or_parse_failed():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="cfg.yaml")
    empty_dat = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="cfg.yaml",
        dat=None,
    )
    bad_dat = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="cfg.yaml",
        dat="{broken",
    )

    empty_item = FakeOpsService([process_cfg], [empty_dat]).get_process_states(date="20260625")[0]
    bad_item = FakeOpsService([process_cfg], [bad_dat]).get_process_states(date="20260625")[0]

    assert empty_item.extra is None
    assert empty_item.status == "normal"
    assert bad_item.extra is None
    assert bad_item.status == "unknown"


def test_process_args_fall_back_to_cfg_value_when_state_missing():
    process_cfg = cfg(
        cfg_type="process",
        cfg_key="tlBinTradeLite",
        value="sys_ZXACFE.yaml",
    )

    item = FakeOpsService([process_cfg], []).get_process_states(date="20260625")[0]

    assert item.args == "sys_ZXACFE.yaml"


def test_process_args_stay_none_when_state_missing_and_cfg_value_empty():
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="")

    item = FakeOpsService([process_cfg], []).get_process_states(date="20260625")[0]

    assert item.args is None


def test_process_args_fall_back_to_cfg_value_when_matched_state_value_is_empty():
    service = FakeOpsService()
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="cfg.yaml")

    for state_value in (None, "", "   "):
        row = state(
            state_type="process",
            state_key="./bin/tlBinTradeLite",
            value=state_value,
        )

        assert service._build_process_item(process_cfg, row).args == "cfg.yaml"


def test_process_args_stay_none_when_matched_state_and_cfg_values_are_empty():
    service = FakeOpsService()
    process_cfg = cfg(cfg_type="process", cfg_key="tlBinTradeLite", value="   ")
    row = state(
        state_type="process",
        state_key="./bin/tlBinTradeLite",
        value="",
    )

    assert service._build_process_item(process_cfg, row).args is None


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
    assert inside.args == "['sys_simnow.yaml']"
    assert inside.pid == 103833
    assert outside.status == "normal"
    assert outside.args == "['sys_simnow.yaml']"
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


def test_process_state_only_is_excluded_by_default_and_added_for_all_group():
    process_cfg = cfg(
        cfg_type="process",
        machine_tag="configured-machine",
        group_name="op",
        cfg_key="tlBinTradeLite",
        value="cfg.yaml",
    )
    matching_state = state(
        state_type="process",
        machine_tag="configured-machine",
        state_key="./bin/tlBinTradeLite",
        value="cfg.yaml state.yaml",
        dat="{'pid': 101, 'cpu': 0.1, 'mem': 200.5}",
    )
    state_only = state(
        state_type="process",
        machine_tag="state-only-machine",
        state_key="./bin/unconfigured",
        value="state-only args",
        dat="{'pname': 'unconfiguredProc', 'pid': 202, 'cpu': 0.2, 'mem': 300.5}",
    )
    service = FakeOpsService([process_cfg], [matching_state, state_only])

    default_items = service.get_process_states(date="20260625")
    all_items = service.get_process_states(date="20260625", include_state_only=True)

    assert [item.process_name for item in default_items] == ["tlBinTradeLite"]
    assert default_items[0].is_configured is True
    assert [item.process_name for item in all_items] == ["tlBinTradeLite", "unconfiguredProc"]

    unconfigured = all_items[1]
    assert unconfigured.machine_tag == "state-only-machine"
    assert unconfigured.group is None
    assert unconfigured.args == "state-only args"
    assert unconfigured.pid == 202
    assert unconfigured.cpu == 0.2
    assert unconfigured.memory == 300.5
    assert unconfigured.status == "normal"
    assert unconfigured.is_configured is False


def test_process_state_only_extra_uses_dat_fields_except_fixed_columns():
    state_only = state(
        state_type="process",
        machine_tag="state-only-machine",
        state_key="./bin/unconfigured",
        value="state-only args",
        dat=(
            "{'pname': 'unconfiguredProc', 'pid': 202, 'cpu': 0.2, "
            "'mem': 300.5, 'strategy_name': 'alpha', 'position': 3}"
        ),
    )

    item = FakeOpsService([], [state_only]).get_process_states(
        date="20260625",
        include_state_only=True,
    )[0]

    assert item.process_name == "unconfiguredProc"
    assert item.args == "state-only args"
    assert item.is_configured is False
    assert item.extra == {"strategy_name": "alpha", "position": 3}


def test_process_state_only_is_not_added_for_specific_group():
    process_cfg = cfg(
        cfg_type="process",
        machine_tag="configured-machine",
        group_name="op",
        cfg_key="tlBinTradeLite",
        value="cfg.yaml",
    )
    state_only = state(
        state_type="process",
        machine_tag="state-only-machine",
        state_key="./bin/unconfigured",
        value="state-only args",
        dat="{'pid': 202}",
    )

    items = FakeOpsService([process_cfg], [state_only]).get_process_states(
        group="op",
        date="20260625",
        include_state_only=True,
    )

    assert len(items) == 1
    assert items[0].machine_tag == "configured-machine"
    assert items[0].is_configured is True


def test_process_state_only_only_error_filter_respects_update_time():
    fresh_state_only = state(
        state_type="process",
        machine_tag="fresh-state-only",
        state_key="./bin/fresh",
        value="fresh args",
        dat="{'pname': 'freshProc', 'pid': 1}",
    )
    stale_state_only = state(
        state_type="process",
        machine_tag="stale-state-only",
        state_key="./bin/stale",
        value="stale args",
        dat="{'pname': 'staleProc', 'pid': 2}",
        update_time=stale_time(),
    )

    items = FakeOpsService([], [fresh_state_only, stale_state_only]).get_process_states(
        date="20260625",
        only_error=True,
        include_state_only=True,
    )

    assert [item.process_name for item in items] == ["staleProc"]
    assert items[0].status == "offline"
    assert items[0].is_configured is False
    assert items[0].args == "stale args"


def test_process_overview_total_does_not_include_state_only():
    state_only = state(
        state_type="process",
        machine_tag="state-only-machine",
        state_key="./bin/unconfigured",
        value="state-only args",
        dat="{'pid': 202}",
    )

    overview = FakeOpsService([], [state_only]).get_overview(date="20260625")

    assert overview.process.total == 0
    assert overview.process.alarm_count == 0


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



class FixedNowLogOpsService(OpsService):
    def _now(self):
        return datetime(2026, 7, 8, 9, 0, 0)


def make_log_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    service = FixedNowLogOpsService(db, settings=fake_settings(OPS_MAX_PAGE_SIZE=100))
    return service, db


def log_row(log_id, date="20260708", machine_tag="m1", log_name="trade", level="info"):
    return OpsLog(
        log_id=log_id,
        date=date,
        machine_tag=machine_tag,
        log_name=log_name,
        level=level,
        log=f"{level} log {log_id}",
        update_time=f"{date} 08:50:0{log_id % 10}",
    )


def cfg_row(machine_tag, group_name):
    return OpsCfg(
        type="os",
        machine_tag=machine_tag,
        group_name=group_name,
        cfg_key="os",
        value="",
        status=1,
    )


def process_cfg_row(machine_tag, group_name, status=1):
    return OpsCfg(
        type="process",
        machine_tag=machine_tag,
        group_name=group_name,
        cfg_key="proc",
        value="",
        status=status,
    )


def seed_log_rows(db):
    db.add_all([
        log_row(1, machine_tag="m1", level="info"),
        log_row(2, machine_tag="m1", level="warn"),
        log_row(3, machine_tag="m2", level="ERROR"),
        log_row(4, date="20260707", machine_tag="m1", level="error"),
    ])
    db.commit()


def test_get_logs_defaults_to_today_and_log_id_desc():
    service, db = make_log_service()
    seed_log_rows(db)

    result = service.get_logs()

    assert result.total == 3
    assert [item.log_id for item in result.items] == [3, 2, 1]


def test_get_logs_filters_by_explicit_date():
    service, db = make_log_service()
    seed_log_rows(db)

    result = service.get_logs(date="20260707")

    assert result.total == 1
    assert result.items[0].log_id == 4


def test_get_logs_only_error_and_level_filters_are_case_insensitive():
    service, db = make_log_service()
    seed_log_rows(db)

    only_error = service.get_logs(only_error=True)
    info = service.get_logs(level="info")
    error = service.get_logs(level="ERROR")

    assert [item.log_id for item in only_error.items] == [3, 2]
    assert [item.log_id for item in info.items] == [1]
    assert [item.log_id for item in error.items] == [3]
    assert error.items[0].level == "error"


def test_get_logs_group_filters_by_ops_cfg_machine_tags():
    service, db = make_log_service()
    seed_log_rows(db)
    db.add_all([cfg_row("m1", "algo00x"), cfg_row("m2", "op")])
    db.commit()

    algo = service.get_logs(group="algo00x")
    op = service.get_logs(group="op")
    missing = service.get_logs(group="missing")

    assert [item.machine_tag for item in algo.items] == ["m1", "m1"]
    assert [item.machine_tag for item in op.items] == ["m2"]
    assert missing.total == 0
    assert missing.items == []


def test_get_logs_filters_by_machine_tag():
    service, db = make_log_service()
    seed_log_rows(db)

    result = service.get_logs(machine_tag="m1")

    assert result.total == 2
    assert [item.machine_tag for item in result.items] == ["m1", "m1"]


def test_get_logs_combines_group_and_machine_tag_filters():
    service, db = make_log_service()
    seed_log_rows(db)
    db.add_all([cfg_row("m1", "algo00x"), cfg_row("m2", "op")])
    db.commit()

    matching = service.get_logs(group="algo00x", machine_tag="m1")
    not_matching = service.get_logs(group="algo00x", machine_tag="m2")

    assert matching.total == 2
    assert [item.machine_tag for item in matching.items] == ["m1", "m1"]
    assert not_matching.total == 0
    assert not_matching.items == []


def test_get_logs_ignores_blank_machine_tag():
    service, db = make_log_service()
    seed_log_rows(db)

    empty = service.get_logs(machine_tag="")
    whitespace = service.get_logs(machine_tag="   ")

    assert empty.total == 3
    assert whitespace.total == 3
    assert [item.log_id for item in whitespace.items] == [3, 2, 1]


def test_get_logs_supports_explicit_sort_and_pagination():
    service, db = make_log_service()
    seed_log_rows(db)

    result = service.get_logs(page=2, page_size=1, sort_by="machine_tag", sort_order="asc")

    assert result.total == 3
    assert result.page == 2
    assert result.page_size == 1
    assert result.items[0].machine_tag == "m1"


def test_get_groups_returns_active_trimmed_distinct_sorted_groups():
    service, db = make_log_service()
    db.add_all([
        cfg_row("m1", " op "),
        cfg_row("m2", "algo00x"),
        cfg_row("m3", "op"),
        cfg_row("m4", ""),
        cfg_row("m5", "   "),
        cfg_row("m6", "\u5168\u90e8"),
        cfg_row("m7", " \u4ec5\u5f02\u5e38 "),
        process_cfg_row("m8", "fut"),
        process_cfg_row("m9", "backup", status=0),
    ])
    db.commit()

    result = service.get_groups()

    assert [item.model_dump() for item in result] == [
        {"group": "algo00x", "display_name": "algo00x"},
        {"group": "fut", "display_name": "fut"},
        {"group": "op", "display_name": "op"},
    ]


class FakeGroupQuery:
    def __init__(self):
        self.filters = []

    def filter(self, *args):
        self.filters.extend(args)
        return self

    def distinct(self):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return []


class FakeGroupDb:
    def __init__(self):
        self.query_obj = FakeGroupQuery()

    def query(self, *args):
        return self.query_obj


def test_get_groups_filters_null_group_values():
    db = FakeGroupDb()
    service = OpsService(db, settings=fake_settings())

    result = service.get_groups()

    assert result == []
    assert any("IS NOT NULL" in str(item) for item in db.query_obj.filters)


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

