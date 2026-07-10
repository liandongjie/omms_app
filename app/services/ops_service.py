# -*- coding: utf-8 -*-
from collections import Counter
from datetime import datetime
from typing import Any, Iterable

from fastapi import Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ops_model import OpsCfg, OpsLog, OpsState
from app.schemas.ops_schema import (
    AlarmItem,
    GroupItem,
    LogItem,
    LogPageResponse,
    OsStateItem,
    OverviewLogStats,
    OverviewOsStats,
    OverviewProcessStats,
    OverviewResponse,
    ProcessStateItem,
)
from app.services.base_service import BaseService
from app.utils.db import get_db
from app.utils.ops_parse import is_in_work_time, is_stale, parse_dat, parse_metric_value, today_yyyymmdd


ABNORMAL_STATUSES = {"warning", "error", "offline", "unknown"}
LOG_ALARM_LEVELS = {"warn", "error"}
LOG_SORT_FIELDS = {"log_id", "date", "machine_tag", "log_name", "level", "update_time"}
RESERVED_GROUP_NAMES = {"\u5168\u90e8", "\u4ec5\u5f02\u5e38"}
PROCESS_EXTRA_EXCLUDED_KEYS = {"pid", "cpu", "mem", "memory", "args", "pname", "process_name"}


class OpsService(BaseService):
    def __init__(self, db: Session, settings=None):
        super().__init__(db)
        self.settings = settings or get_settings()

    def _now(self) -> datetime:
        return datetime.now()

    def get_overview(self, group: str | None = None, only_error: bool = False, date: str | None = None) -> OverviewResponse:
        target_date = date or today_yyyymmdd()
        os_items = self.get_os_states(group=group, only_error=only_error, date=target_date)
        process_items = self.get_process_states(group=group, only_error=only_error, date=target_date)
        log_stats = self._get_log_stats(group=group, date=target_date, only_error=only_error)

        return OverviewResponse(
            os=OverviewOsStats(
                total=len(os_items),
                monitor_items=len(os_items),
                abnormal_count=sum(1 for item in os_items if item.status in ABNORMAL_STATUSES),
                alarm_count=sum(1 for item in os_items if item.status in ABNORMAL_STATUSES),
            ),
            process=OverviewProcessStats(
                total=len(process_items),
                running_count=sum(1 for item in process_items if item.status == "normal"),
                abnormal_count=sum(1 for item in process_items if item.status in ABNORMAL_STATUSES),
                alarm_count=sum(1 for item in process_items if item.status in ABNORMAL_STATUSES),
            ),
            log=log_stats,
        )

    def get_os_states(self, group: str | None = None, only_error: bool = False, date: str | None = None) -> list[OsStateItem]:
        target_date = date or today_yyyymmdd()
        cfgs = self._get_active_cfgs("os", group)
        states = self._get_states("os", target_date)
        state_map = {(state.machine_tag, state.state_key): state for state in states}

        items = [self._build_os_item(cfg, state_map.get((cfg.machine_tag, cfg.cfg_key))) for cfg in cfgs]
        return self._filter_error_items(items, only_error)

    def get_process_states(
        self,
        group: str | None = None,
        only_error: bool = False,
        date: str | None = None,
        include_state_only: bool = False,
    ) -> list[ProcessStateItem]:
        target_date = date or today_yyyymmdd()
        is_all_group = self._is_all_group(group)
        cfgs = self._get_active_cfgs("process", None if is_all_group else group)
        states = self._get_states("process", target_date)

        items = []
        matched_state_ids = set()
        for cfg in cfgs:
            state = self._find_process_state(cfg, states)
            if state is not None:
                matched_state_ids.add(self._state_identity(state))
            items.append(self._build_process_item(cfg, state))

        if include_state_only and is_all_group:
            items.extend(
                self._build_state_only_process_item(state)
                for state in states
                if self._state_identity(state) not in matched_state_ids
            )

        return self._filter_error_items(items, only_error)

    def get_logs(
        self,
        group: str | None = None,
        machine_tag: str | None = None,
        level: str | None = None,
        date: str | None = None,
        page: int = 1,
        page_size: int = 20,
        only_error: bool = False,
        sort_by: str | None = "",
        sort_order: str | None = "",
    ) -> LogPageResponse:
        target_date = date or today_yyyymmdd(self._now())
        page = max(page, 1)
        max_page_size = getattr(self.settings, "OPS_MAX_PAGE_SIZE", 200)
        page_size = min(max(page_size, 1), max_page_size)

        machine_tags = self._get_group_machine_tags(group) if group else None
        query = self.db.query(OpsLog).filter(OpsLog.date == target_date)
        if machine_tag:
            query = query.filter(OpsLog.machine_tag == machine_tag)

        normalized_level = (level or "").strip().lower()
        if normalized_level:
            query = query.filter(func.lower(OpsLog.level) == normalized_level)
        elif only_error:
            query = query.filter(func.lower(OpsLog.level).in_(LOG_ALARM_LEVELS))

        if machine_tags is not None:
            if not machine_tags:
                return LogPageResponse(items=[], total=0, page=page, page_size=page_size)
            query = query.filter(OpsLog.machine_tag.in_(machine_tags))

        total = query.count()
        sort_field = sort_by or "log_id"
        if sort_field not in LOG_SORT_FIELDS:
            raise ValueError(f"unsupported sort_by: {sort_by}")
        sort_column = getattr(OpsLog, sort_field)
        if sort_order == "asc":
            order_by = sort_column.asc()
        else:
            order_by = sort_column.desc()

        logs = (
            query.order_by(order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        group_map = self._get_machine_group_map()
        return LogPageResponse(
            items=[self._build_log_item(log, group_map.get(log.machine_tag)) for log in logs],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_alarms(self, group: str | None = None, date: str | None = None) -> list[AlarmItem]:
        target_date = date or today_yyyymmdd()
        alarms: list[AlarmItem] = []

        for item in self.get_os_states(group=group, only_error=True, date=target_date):
            alarms.append(
                AlarmItem(
                    type="os",
                    level=item.status,
                    machine_tag=item.machine_tag,
                    group=item.group,
                    target="os",
                    message=item.message,
                    update_time=item.update_time,
                )
            )

        for item in self.get_process_states(group=group, only_error=True, date=target_date):
            alarms.append(
                AlarmItem(
                    type="process",
                    level=item.status,
                    machine_tag=item.machine_tag,
                    group=item.group,
                    target=item.process_name,
                    message=item.message,
                    update_time=item.update_time,
                )
            )

        logs = self.get_logs(group=group, date=target_date, page=1, page_size=200)
        for item in logs.items:
            level = (item.level or "").lower()
            if level not in {"warn", "error"}:
                continue
            alarms.append(
                AlarmItem(
                    type="log",
                    level="warning" if level == "warn" else "error",
                    machine_tag=item.machine_tag,
                    group=item.group,
                    target=item.log_name,
                    message=item.log or "",
                    update_time=item.update_time,
                )
            )

        return alarms

    def get_groups(self) -> list[GroupItem]:
        trimmed_group = func.trim(OpsCfg.group_name)
        rows = (
            self.db.query(trimmed_group.label("group_name"))
            .filter(
                OpsCfg.status == 1,
                OpsCfg.group_name.isnot(None),
                trimmed_group != "",
                ~trimmed_group.in_(RESERVED_GROUP_NAMES),
            )
            .distinct()
            .order_by(trimmed_group.asc())
            .all()
        )
        return [GroupItem(group=row[0], display_name=row[0]) for row in rows if row[0]]

    def _get_active_cfgs(self, cfg_type: str, group: str | None = None) -> list[OpsCfg]:
        query = self.db.query(OpsCfg).filter(OpsCfg.type == cfg_type, OpsCfg.status == 1)
        if group:
            query = query.filter(OpsCfg.group_name == group)
        return query.all()

    def _get_states(self, state_type: str, date: str) -> list[OpsState]:
        return self.db.query(OpsState).filter(OpsState.type == state_type, OpsState.date == date).all()

    def _get_group_machine_tags(self, group: str | None) -> list[str]:
        if not group:
            return []
        rows = (
            self.db.query(OpsCfg.machine_tag)
            .filter(OpsCfg.group_name == group, OpsCfg.status == 1)
            .distinct()
            .all()
        )
        return [row[0] for row in rows if row[0]]

    def _get_machine_group_map(self) -> dict[str, str]:
        rows = (
            self.db.query(OpsCfg.machine_tag, OpsCfg.group_name)
            .filter(OpsCfg.status == 1)
            .distinct()
            .all()
        )
        return {machine_tag: group_name for machine_tag, group_name in rows if machine_tag}

    def _get_log_stats(self, group: str | None, date: str, only_error: bool = False) -> OverviewLogStats:
        machine_tags = self._get_group_machine_tags(group) if group else None
        query = self.db.query(OpsLog.level).filter(OpsLog.date == date)
        if machine_tags is not None:
            if not machine_tags:
                return OverviewLogStats()
            query = query.filter(OpsLog.machine_tag.in_(machine_tags))

        levels = Counter((row[0] or "").lower() for row in query.all())
        error_count = levels["error"]
        warn_count = levels["warn"]
        total = error_count + warn_count if only_error else sum(levels.values())
        return OverviewLogStats(
            total=total,
            error_count=error_count,
            warn_count=warn_count,
            alarm_count=error_count + warn_count,
        )

    def _build_os_item(self, cfg: OpsCfg, state: OpsState | None) -> OsStateItem:
        now = self._now()
        monitoring_now = is_in_work_time(cfg.work_time, now=now)

        if state is None:
            status = "offline" if monitoring_now else "normal"
            message = "latest os state not found" if monitoring_now else "outside work time; latest os state not found"
            return OsStateItem(
                machine_tag=cfg.machine_tag,
                group=cfg.group_name,
                status=status,
                message=message,
            )

        data = parse_dat(state.dat)
        cpu = parse_metric_value(data.get("cpu"))
        mem = parse_metric_value(data.get("mem"))
        disk = parse_metric_value(data.get("disk"))
        cpu_alarm = int(cpu is not None and cpu >= self.settings.OPS_CPU_ALARM_THRESHOLD)
        mem_alarm = int(mem is not None and mem >= self.settings.OPS_MEM_ALARM_THRESHOLD)
        disk_alarm = int(disk is not None and disk >= self.settings.OPS_DISK_ALARM_THRESHOLD)

        offline_minutes = self.settings.OPS_OFFLINE_TIMEOUT_MINUTES
        if monitoring_now and is_stale(state.update_time, minutes=offline_minutes, now=now):
            status = "offline"
            message = f"os state not updated within {offline_minutes} minutes"
        elif state.dat and not data:
            status = "unknown"
            message = "os state data parse failed"
        elif cpu is None or mem is None or disk is None:
            status = "unknown"
            message = "os state data missing"
        elif cpu >= self.settings.OPS_CPU_ALARM_THRESHOLD:
            status = "error"
            message = f"CPU usage too high: {cpu:g}"
        elif mem >= self.settings.OPS_MEM_ALARM_THRESHOLD:
            status = "error"
            message = f"memory usage too high: {mem:g}"
        elif disk >= self.settings.OPS_DISK_ALARM_THRESHOLD:
            status = "error"
            message = f"disk usage too high: {disk:g}"
        else:
            status = "normal"
            message = "normal"

        return OsStateItem(
            machine_tag=cfg.machine_tag,
            group=cfg.group_name,
            cpu_usage=cpu,
            memory_usage=mem,
            disk_usage=disk,
            cpu_alarm=cpu_alarm,
            mem_alarm=mem_alarm,
            disk_alarm=disk_alarm,
            status=status,
            message=message,
            update_time=state.update_time,
        )

    @staticmethod
    def _find_process_state(cfg: OpsCfg, states: Iterable[OpsState]) -> OpsState | None:
        cfg_key = cfg.cfg_key or ""
        cfg_value = cfg.value or ""
        for state in states:
            if state.machine_tag != cfg.machine_tag:
                continue

            if state.type != cfg.type:
                continue

            state_key = state.state_key or ""
            if cfg_key not in state_key:
                continue

            if cfg_value and cfg_value not in (state.value or ""):
                continue

            return state
        return None

    @staticmethod
    def _state_identity(state: OpsState) -> tuple:
        return (state.date, state.type, state.machine_tag, state.state_key, state.value)

    @staticmethod
    def _is_all_group(group: str | None) -> bool:
        return group is None or not group.strip() or group.strip().lower() == "all"

    def _build_process_item(self, cfg: OpsCfg, state: OpsState | None) -> ProcessStateItem:
        now = self._now()
        monitoring_now = is_in_work_time(cfg.work_time, now=now)

        if state is None:
            status = "offline" if monitoring_now else "normal"
            message = "latest process state not found" if monitoring_now else "outside work time; latest process state not found"
            return ProcessStateItem(
                machine_tag=cfg.machine_tag,
                group=cfg.group_name,
                process_name=cfg.cfg_key,
                is_configured=True,
                status=status,
                message=message,
            )

        offline_minutes = self.settings.OPS_OFFLINE_TIMEOUT_MINUTES
        data = parse_dat(state.dat)
        if monitoring_now and is_stale(state.update_time, minutes=offline_minutes, now=now):
            status = "offline"
            message = f"process state not updated within {offline_minutes} minutes"
        elif state.dat and not data:
            status = "unknown"
            message = "process state data parse failed"
        else:
            status = "normal"
            message = "normal"

        args = self._normalize_process_args(state.value)

        return ProcessStateItem(
            machine_tag=cfg.machine_tag,
            group=cfg.group_name,
            process_name=cfg.cfg_key,
            args=args,
            pid=data.get("pid"),
            cpu=data.get("cpu"),
            memory=data.get("mem", data.get("memory")),
            is_configured=True,
            status=status,
            message=message,
            update_time=state.update_time,
            extra=self._extract_process_extra(data),
        )

    def _build_state_only_process_item(self, state: OpsState) -> ProcessStateItem:
        now = self._now()
        offline_minutes = self.settings.OPS_OFFLINE_TIMEOUT_MINUTES
        data = parse_dat(state.dat)
        process_name = self._normalize_process_name(data.get("pname")) or state.state_key or ""

        if is_stale(state.update_time, minutes=offline_minutes, now=now):
            status = "offline"
            message = f"process state not updated within {offline_minutes} minutes"
        else:
            status = "normal"
            message = "normal"

        return ProcessStateItem(
            machine_tag=state.machine_tag,
            group=None,
            process_name=process_name,
            args=self._normalize_process_args(state.value),
            pid=data.get("pid"),
            cpu=data.get("cpu"),
            memory=data.get("mem", data.get("memory")),
            is_configured=False,
            status=status,
            message=message,
            update_time=state.update_time,
            extra=self._extract_process_extra(data),
        )

    @staticmethod
    def _extract_process_extra(data: dict[str, Any]) -> dict[str, Any] | None:
        extra = {
            key: value
            for key, value in data.items()
            if key not in PROCESS_EXTRA_EXCLUDED_KEYS
        }
        return extra or None

    @staticmethod
    def _normalize_process_args(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _normalize_process_name(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _build_log_item(log: OpsLog, group: str | None = None) -> LogItem:
        return LogItem(
            log_id=log.log_id,
            date=log.date,
            machine_tag=log.machine_tag,
            group=group,
            log_name=log.log_name,
            level=(log.level or "").lower(),
            log=log.log,
            update_time=log.update_time,
        )

    @staticmethod
    def _filter_error_items(items: list, only_error: bool) -> list:
        if not only_error:
            return items
        return [item for item in items if item.status in ABNORMAL_STATUSES]


def get_ops_service(db: Session = Depends(get_db)) -> OpsService:
    return OpsService(db)

