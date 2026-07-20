# -*- coding: utf-8 -*-
# 导入依赖
import logging
from collections import Counter, OrderedDict
from datetime import datetime, time
from threading import Lock
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
from app.utils.ops_parse import (
    is_in_work_time,
    is_stale,
    parse_dat,
    parse_metric_value,
    parse_process_args,
    parse_update_time,
    today_yyyymmdd,
)

logger = logging.getLogger(__name__)

# 定义公共常量
ABNORMAL_STATUSES = {
    "warning",  # 警告
    "error",  # 指标超限等错误
    "offline",  # 离线（应该在线但没有有效上报）
    "unknown",  # 数据缺失或解析失败
}
LOG_ALARM_LEVELS = {"warn", "error"}
LOG_SORT_FIELDS = {"log_id", "date", "machine_tag", "log_name", "level", "update_time"}
RESERVED_GROUP_NAMES = {"\u5168\u90e8", "\u4ec5\u5f02\u5e38"}
PROCESS_EXTRA_EXCLUDED_KEYS = {
    "pid",
    "cpu",
    "mem",
    "memory",
    "args",
    "pname",
    "process_name",
}
PROCESS_WARNING_CACHE_MAXSIZE = 1024
PROCESS_AM_START = time(8, 0, 0)
PROCESS_PM_START = time(18, 0, 0)
SENSITIVE_PROCESS_ARG_NAMES = {
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "dsn",
    "database_url",
    "database-url",
    "db_url",
    "db-url",
    "connection_string",
    "connection-string",
}
_PROCESS_WARNING_KEYS: OrderedDict[tuple, None] = OrderedDict()
_PROCESS_WARNING_LOCK = Lock()


def _should_log_process_warning(key: tuple) -> bool:
    """Register a warning key in the bounded process-local LRU cache."""
    with _PROCESS_WARNING_LOCK:
        if key in _PROCESS_WARNING_KEYS:
            _PROCESS_WARNING_KEYS.move_to_end(key)
            return False

        _PROCESS_WARNING_KEYS[key] = None
        if len(_PROCESS_WARNING_KEYS) > PROCESS_WARNING_CACHE_MAXSIZE:
            _PROCESS_WARNING_KEYS.popitem(last=False)
        return True


def _log_process_warning_once(key: tuple, message: str, *args: Any) -> None:
    # Logging stays outside the cache lock so slow handlers cannot block polling requests.
    should_log = _should_log_process_warning(key)
    if should_log:
        logger.warning(message, *args)


class OpsService(BaseService):
    """汇总运维配置、最新状态和日志，生成监控查询所需的领域结果。

    ``ops_cfg`` 定义启用的监控项、所属分组和工作时间；``ops_state`` 保存按日期、
    类型和机器等维度区分的最新上报状态；``ops_log`` 保存独立的日志记录。OS 和
    进程视图以配置为入口匹配状态，日志则通过启用配置中的机器标签补充分组信息。
    本服务统一负责这些数据的筛选、状态判定，以及总览、分组和告警结果的组装。
    """

    def __init__(self, db: Session, settings=None):
        super().__init__(db)
        self.settings = settings or get_settings()

    def _now(self) -> datetime:
        return datetime.now()

    def get_overview(
        self,
        group: str | None = None,
        only_error: bool = False,
        date: str | None = None,
    ) -> OverviewResponse:
        """
        获取监控概览统计信息

        Args:
            group: 分组名称，为 None、空字符串或 "all" 时表示查询全部分组
            only_error: 是否仅统计异常状态的数据，默认 False 统计全部
            date: 查询日期，格式为 YYYYMMDD，默认使用当天日期

        Returns:
            OverviewResponse: 概览响应对象，包含OS、进程、日志三大类统计信息
        """
        # 复用各明细查询的筛选和状态判定，保证总览计数与同条件下的明细口径一致。
        target_date = date or today_yyyymmdd()
        os_items = self.get_os_states(
            group=group, only_error=only_error, date=target_date
        )
        process_items = self.get_process_states(
            group=group, only_error=only_error, date=target_date
        )
        log_stats = self._get_log_stats(
            group=group, date=target_date, only_error=only_error
        )

        return OverviewResponse(
            os=OverviewOsStats(
                total=len(os_items),
                monitor_items=len(os_items),
                abnormal_count=sum(
                    1 for item in os_items if item.status in ABNORMAL_STATUSES
                ),
                alarm_count=sum(
                    1 for item in os_items if item.status in ABNORMAL_STATUSES
                ),
            ),
            process=OverviewProcessStats(
                total=len(process_items),
                running_count=sum(
                    1 for item in process_items if item.status == "normal"
                ),
                abnormal_count=sum(
                    1 for item in process_items if item.status in ABNORMAL_STATUSES
                ),
                alarm_count=sum(
                    1 for item in process_items if item.status in ABNORMAL_STATUSES
                ),
            ),
            log=log_stats,
        )

    def get_os_states(
        self,
        group: str | None = None,
        only_error: bool = False,
        date: str | None = None,
    ) -> list[OsStateItem]:
        """
        获取操作系统监控状态列表

        Args:
            group: 分组名称，为 None、空字符串或 "all" 时表示查询全部分组
            only_error: 是否仅返回异常状态的 OS，默认 False 返回所有状态
            date: 查询日期，格式为 YYYYMMDD，默认使用当天日期

        Returns:
            操作系统状态项列表，每个项包含主机标签、分组、资源使用率等信息
        """
        # 确定目标日期，默认使用当天
        target_date = date or today_yyyymmdd()
        # 获取活动的 OS 监控配置
        cfgs = self._get_active_cfgs("os", group)
        # 获取指定日期的 OS 状态记录
        states = self._get_states("os", target_date)
        # 将状态记录转换为字典，便于快速查找（key: (machine_tag, state_key)）
        state_map = {(state.machine_tag, state.state_key): state for state in states}

        # 为每个配置匹配对应的状态，构建 OS 状态项列表
        items = [
            self._build_os_item(cfg, state_map.get((cfg.machine_tag, cfg.cfg_key)))
            for cfg in cfgs
        ]
        # 根据 only_error 参数过滤结果
        return self._filter_error_items(items, only_error)

    def get_process_states(
        self,
        group: str | None = None,
        only_error: bool = False,
        date: str | None = None,
        include_state_only: bool = False,
    ) -> list[ProcessStateItem]:
        """
        获取进程监控状态列表

        Args:
            group: 分组名称，为 None、空字符串或 "all" 时表示查询全部分组
            only_error: 是否仅返回异常状态的进程，默认 False 返回所有状态
            date: 查询日期，格式为 YYYYMMDD，默认使用当天日期
            include_state_only: 是否包含只有状态记录但无对应配置的进程，仅在全部分组查询时生效

        Returns:
            进程状态项列表，每个项包含进程配置信息和对应的监控状态
        """
        now = self._now()
        # 确定目标日期，默认使用本次请求统一时钟对应的当天。
        target_date = date or today_yyyymmdd(now)
        # 判断是否为全部分组查询
        is_all_group = self._is_all_group(group)
        # 获取活动的进程监控配置（全部分组时不传分组参数）
        cfgs = self._get_active_cfgs("process", None if is_all_group else group)
        # 获取指定日期的进程状态记录
        states = self._get_states("process", target_date)

        items = []
        matched_state_ids = set()
        # 遍历配置，为每个配置收集全部候选后再选择当前盘次的状态。
        for cfg in cfgs:
            candidates = self._find_process_state_candidates(cfg, states)
            classified = [
                (state, self._classify_process_session(state))
                for state in candidates
            ]
            am_candidates = [state for state, session in classified if session == "am"]
            pm_candidates = [state for state, session in classified if session == "pm"]
            ambiguous_candidates = [
                state for state, session in classified if session == "ambiguous"
            ]
            generic_candidates = [
                state for state, session in classified if session == "generic"
            ]

            for state in candidates:
                self._warn_if_process_args_mismatch(state)
            for state in ambiguous_candidates:
                self._warn_ambiguous_process_state(state)

            session_mode = bool(
                am_candidates or pm_candidates or ambiguous_candidates
            )
            if session_mode:
                # 全部明确盘次及盘次不明的候选都属于 cfg；未选中的盘次也不能
                # 在后续 state-only 处理中被误报为“未配置进程”。
                matched_state_ids.update(
                    self._state_identity(state)
                    for state in am_candidates + pm_candidates + ambiguous_candidates
                )
                if generic_candidates:
                    self._warn_mixed_process_candidates(
                        cfg,
                        am_candidates + pm_candidates + ambiguous_candidates,
                        generic_candidates,
                    )

                # 盘次必须按本次请求统一的当前时间选择；目标盘次缺失时不能
                # 回退到另一盘次或 generic，否则会展示旧盘次的进程指标。
                target_session = (
                    "am" if PROCESS_AM_START <= now.time() < PROCESS_PM_START else "pm"
                )
                target_candidates = (
                    am_candidates if target_session == "am" else pm_candidates
                )
                selected_state = self._select_latest_process_state(target_candidates)
            else:
                # 普通模式同样收集全部候选，避免重复或历史状态变成 state-only。
                matched_state_ids.update(
                    self._state_identity(state) for state in generic_candidates
                )
                selected_state = self._select_latest_process_state(generic_candidates)

            items.append(self._build_process_item(cfg, selected_state, now=now))

        # 若需要包含独立状态项且为全部分组查询，补充未匹配到配置的状态
        # matched_state_ids 用于避免已被配置消费的状态再次以“未配置进程”出现。
        if include_state_only and is_all_group:
            items.extend(
                self._build_state_only_process_item(state, now=now)
                for state in states
                if self._state_identity(state) not in matched_state_ids
            )

        # 根据 only_error 参数过滤异常项
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
        """
        获取日志分页列表

        Args:
            group: 分组名称，用于过滤指定分组的机器日志
            machine_tag: 机器标签，精确匹配指定机器的日志
            level: 日志级别（如 warn、error），大小写不敏感
            date: 查询日期，格式为 YYYYMMDD，默认使用当天日期
            page: 页码，默认第 1 页，最小值为 1
            page_size: 每页大小，默认 20，范围 1~OPS_MAX_PAGE_SIZE（默认200）
            only_error: 是否仅查询错误级别日志（warn/error），默认 False
            sort_by: 排序字段，支持 log_id/date/machine_tag/log_name/level/update_time
            sort_order: 排序顺序，"asc" 升序，其他值或空为降序

        Returns:
            LogPageResponse: 日志分页响应，包含日志列表、总数、页码、每页大小

        Raises:
            ValueError: 当 sort_by 参数不在支持的字段列表中时抛出
        """

        target_date = date or today_yyyymmdd(self._now())
        page = max(page, 1)
        max_page_size = getattr(self.settings, "OPS_MAX_PAGE_SIZE", 200)
        page_size = min(max(page_size, 1), max_page_size)

        # 日志自身没有分组字段，分组筛选先从启用配置换算成机器标签集合。
        machine_tags = self._get_group_machine_tags(group) if group else None
        machine_tag = (machine_tag or "").strip()
        query = self.db.query(OpsLog).filter(OpsLog.date == target_date)
        if machine_tag:
            query = query.filter(OpsLog.machine_tag == machine_tag)

        normalized_level = (level or "").strip().lower()
        # 显式 level 比“仅异常”更具体；两者同时传入时只按指定级别过滤。
        if normalized_level:
            query = query.filter(func.lower(OpsLog.level) == normalized_level)
        elif only_error:
            query = query.filter(func.lower(OpsLog.level).in_(LOG_ALARM_LEVELS))

        if machine_tags is not None:
            if not machine_tags:
                return LogPageResponse(
                    items=[], total=0, page=page, page_size=page_size
                )
            query = query.filter(OpsLog.machine_tag.in_(machine_tags))

        # 先统计过滤后的总数，再由数据库执行排序、偏移和限量，避免分页后丢失总数。
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
        # 返回结果的分组来自启用配置，仅用于补充展示，不参与前面的日志字段查询。
        group_map = self._get_machine_group_map()
        return LogPageResponse(
            items=[
                self._build_log_item(log, group_map.get(log.machine_tag))
                for log in logs
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_alarms(
        self, group: str | None = None, date: str | None = None
    ) -> list[AlarmItem]:
        """合并 OS、进程异常项与 warn/error 日志，形成统一告警列表。

        OS 和进程复用各自的异常过滤规则；日志告警只处理此处分页调用实际返回的
        第一页，并把 ``warn`` 映射为统一的 ``warning`` 级别。
        """
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

        for item in self.get_process_states(
            group=group, only_error=True, date=target_date
        ):
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
        """从启用配置中提取可筛选分组，并排除空值和界面保留名称。"""
        trimmed_group = func.trim(OpsCfg.group_name)
        rows = (
            self.db.query(trimmed_group.label("group_name"))
            .filter(
                OpsCfg.status == 1,  # 状态为启用
                OpsCfg.group_name.isnot(None),  # 分组名不为空
                trimmed_group != "",  # 去除空格后不为空字符串
                ~trimmed_group.in_(RESERVED_GROUP_NAMES),  # 不在保留名称列表中
            )
            .distinct()  # 去重
            .order_by(trimmed_group.asc())  # 按分组名字母升序排序
            .all()  # 执行查询，获取所有结果
        )
        """
        等价的SQL查询大致如下：
        ```
        SELECT DISTINCT TRIM(`group`) AS group_name
        FROM ops_cfg
        WHERE 
            status = 1
            AND `group` IS NOT NULL
            AND TRIM(`group`) != ''
            AND TRIM(`group`) NOT IN ('全部', '仅异常')
        ORDER BY TRIM(`group`) ASC;
        ```
        """

        return [GroupItem(group=row[0], display_name=row[0]) for row in rows if row[0]]

    def _get_active_cfgs(self, cfg_type: str, group: str | None = None) -> list[OpsCfg]:
        query = self.db.query(OpsCfg).filter(
            OpsCfg.type == cfg_type, OpsCfg.status == 1
        )
        if group:
            query = query.filter(OpsCfg.group_name == group)
        return query.all()

    def _get_states(self, state_type: str, date: str) -> list[OpsState]:
        return (
            self.db.query(OpsState)
            .filter(OpsState.type == state_type, OpsState.date == date)
            .all()
        )

    def _get_group_machine_tags(self, group: str | None) -> list[str]:
        # 分组与日志之间通过启用配置的 machine_tag 间接关联。
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
        return {
            machine_tag: group_name for machine_tag, group_name in rows if machine_tag
        }

    def _get_log_stats(
        self, group: str | None, date: str, only_error: bool = False
    ) -> OverviewLogStats:
        # 与日志列表保持相同的分组口径：先由配置确定该组包含的机器。
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

        # 工作时间内缺少上报才视为离线；工作时间外不因“无状态”产生离线告警。
        if state is None:
            status = "offline" if monitoring_now else "normal"
            message = (
                "latest os state not found"
                if monitoring_now
                else "outside work time; latest os state not found"
            )
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
        disk_home = parse_metric_value(data.get("disk_home"))
        # 负数 disk_home 在这里按无有效指标处理，也不会参与阈值告警。
        if disk_home is not None and disk_home < 0:
            disk_home = None
        cpu_alarm = int(
            cpu is not None and cpu >= self.settings.OPS_CPU_ALARM_THRESHOLD
        )
        mem_alarm = int(
            mem is not None and mem >= self.settings.OPS_MEM_ALARM_THRESHOLD
        )
        disk_alarm = int(
            disk is not None and disk >= self.settings.OPS_DISK_ALARM_THRESHOLD
        )
        disk_home_alarm = int(
            disk_home is not None
            and disk_home >= self.settings.OPS_DISK_ALARM_THRESHOLD
        )

        offline_minutes = self.settings.OPS_OFFLINE_TIMEOUT_MINUTES
        # 判定有明确优先级：工作时间内超时优先，其次是解析/必需指标缺失，
        # 再依次检查资源阈值；工作时间外只跳过超时判断，不跳过数据和阈值检查。
        if monitoring_now and is_stale(
            state.update_time, minutes=offline_minutes, now=now
        ):
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
        elif disk_home_alarm:
            status = "error"
            message = f"disk_home usage too high: {disk_home:g}"
        else:
            status = "normal"
            message = "normal"

        return OsStateItem(
            machine_tag=cfg.machine_tag,
            group=cfg.group_name,
            cpu_usage=cpu,
            memory_usage=mem,
            disk_usage=disk,
            disk_home_usage=disk_home,
            cpu_alarm=cpu_alarm,
            mem_alarm=mem_alarm,
            disk_alarm=disk_alarm,
            disk_home_alarm=disk_home_alarm,
            status=status,
            message=message,
            update_time=state.update_time,
        )

    @staticmethod
    def _find_process_state_candidates(
        cfg: OpsCfg, states: Iterable[OpsState]
    ) -> list[OpsState]:
        """Collect every state satisfying the existing cfg containment rules."""
        cfg_key = cfg.cfg_key or ""
        cfg_value = cfg.value or ""
        candidates = []
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

            candidates.append(state)
        return candidates

    @staticmethod
    def _classify_process_session(state: OpsState) -> str:
        """Classify a state by AM/PM YAML filename suffixes in state.value."""
        sessions = set()
        for argument in parse_process_args(state.value):
            normalized = argument.strip().lower()
            if normalized.endswith("_am.yaml"):
                sessions.add("am")
            if normalized.endswith("_pm.yaml"):
                sessions.add("pm")

        if len(sessions) > 1:
            return "ambiguous"
        if sessions:
            return sessions.pop()
        return "generic"

    @classmethod
    def _select_latest_process_state(
        cls, states: Iterable[OpsState]
    ) -> OpsState | None:
        """Select the newest state without using runtime metrics as tie-breakers."""

        def sort_key(state: OpsState) -> tuple:
            update_time = parse_update_time(state.update_time)
            return (
                update_time is not None,
                update_time or datetime.min,
                cls._state_sort_identity(state),
            )

        return max(states, key=sort_key, default=None)

    @staticmethod
    def _state_identity(state: OpsState) -> tuple:
        return (state.date, state.type, state.machine_tag, state.state_key, state.value)

    @staticmethod
    def _state_sort_identity(state: OpsState) -> tuple[str, ...]:
        return tuple(
            "" if value is None else str(value)
            for value in (
                state.date,
                state.type,
                state.machine_tag,
                state.state_key,
                state.value,
            )
        )

    @staticmethod
    def _redact_process_args(arguments: Iterable[Any]) -> tuple[str, ...]:
        redacted = []
        redact_next = False
        for argument in arguments:
            text = str(argument)
            if redact_next:
                redacted.append("***")
                redact_next = False
                continue

            normalized = text.lstrip("-").lower()
            name, separator, _ = normalized.partition("=")
            if separator and name in SENSITIVE_PROCESS_ARG_NAMES:
                redacted.append(f"{text.split('=', 1)[0]}=***")
            elif normalized in SENSITIVE_PROCESS_ARG_NAMES:
                redacted.append(text)
                redact_next = True
            elif "://" in text and "@" in text:
                redacted.append("***")
            else:
                redacted.append(text)
        return tuple(redacted)

    def _warning_state_identity(self, state: OpsState) -> tuple:
        return (
            state.date,
            state.type,
            state.machine_tag,
            state.state_key,
            self._redact_process_args(parse_process_args(state.value)),
        )

    def _warn_if_process_args_mismatch(self, state: OpsState) -> None:
        data = parse_dat(state.dat)
        dat_args = data.get("args")
        if not isinstance(dat_args, list):
            return

        state_args = parse_process_args(state.value)
        normalized_dat_args = [str(argument) for argument in dat_args]
        if state_args == normalized_dat_args:
            return

        key = (
            "args_mismatch",
            self._state_sort_identity(state),
            tuple(normalized_dat_args),
        )
        _log_process_warning_once(
            key,
            "process state args mismatch: date=%r machine_tag=%r state_key=%r "
            "state_value=%r dat_args=%r",
            state.date,
            state.machine_tag,
            state.state_key,
            self._redact_process_args(state_args),
            self._redact_process_args(normalized_dat_args),
        )

    def _warn_ambiguous_process_state(self, state: OpsState) -> None:
        key = ("ambiguous_session", self._state_sort_identity(state))
        _log_process_warning_once(
            key,
            "process state contains both AM and PM args: date=%r machine_tag=%r "
            "state_key=%r state_value=%r",
            state.date,
            state.machine_tag,
            state.state_key,
            self._redact_process_args(parse_process_args(state.value)),
        )

    def _warn_mixed_process_candidates(
        self,
        cfg: OpsCfg,
        session_candidates: Iterable[OpsState],
        generic_candidates: Iterable[OpsState],
    ) -> None:
        session_identities = tuple(
            sorted(self._state_sort_identity(state) for state in session_candidates)
        )
        generic_identities = tuple(
            sorted(self._state_sort_identity(state) for state in generic_candidates)
        )
        cfg_identity = tuple(
            "" if value is None else str(value)
            for value in (cfg.type, cfg.machine_tag, cfg.cfg_key, cfg.value)
        )
        key = (
            "session_generic_mixed",
            cfg_identity,
            session_identities,
            generic_identities,
        )
        _log_process_warning_once(
            key,
            "process cfg matched session and generic states: machine_tag=%r "
            "cfg_key=%r cfg_value=%r session_states=%r generic_states=%r",
            cfg.machine_tag,
            cfg.cfg_key,
            self._redact_process_args(parse_process_args(cfg.value)),
            tuple(self._warning_state_identity(state) for state in session_candidates),
            tuple(self._warning_state_identity(state) for state in generic_candidates),
        )

    @staticmethod
    def _is_all_group(group: str | None) -> bool:
        return group is None or not group.strip() or group.strip().lower() == "all"

    def _build_process_item(
        self,
        cfg: OpsCfg,
        state: OpsState | None,
        now: datetime | None = None,
    ) -> ProcessStateItem:
        now = now or self._now()
        monitoring_now = is_in_work_time(cfg.work_time, now=now)

        # 有效的实际上报参数优先；state.value 为空时才用 cfg.value 兜底。
        # cfg.value 只原样补充已配置参数，不能推测或补全实际启动参数。
        state_args = self._normalize_process_args(state.value) if state is not None else None
        args = state_args or self._normalize_process_args(cfg.value)

        # 与 OS 一致，配置项只在工作时间内因缺少对应状态被判为离线。
        if state is None:
            status = "offline" if monitoring_now else "normal"
            message = (
                "latest process state not found"
                if monitoring_now
                else "outside work time; latest process state not found"
            )
            return ProcessStateItem(
                machine_tag=cfg.machine_tag,
                group=cfg.group_name,
                process_name=cfg.cfg_key,
                args=args,
                is_configured=True,
                status=status,
                message=message,
            )

        offline_minutes = self.settings.OPS_OFFLINE_TIMEOUT_MINUTES
        data = parse_dat(state.dat)
        # 配置进程只判断上报时效和 dat 是否可解析，不对 CPU、内存数值做阈值判定。
        if monitoring_now and is_stale(
            state.update_time, minutes=offline_minutes, now=now
        ):
            status = "offline"
            message = f"process state not updated within {offline_minutes} minutes"
        elif state.dat and not data:
            status = "unknown"
            message = "process state data parse failed"
        else:
            status = "normal"
            message = "normal"

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

    def _build_state_only_process_item(
        self, state: OpsState, now: datetime | None = None
    ) -> ProcessStateItem:
        # state-only 没有对应 cfg，无法取得分组和工作时间，因此仅按上报时效判定离线；
        # is_configured=False 让调用方能够区分它与配置驱动的进程项。
        now = now or self._now()
        offline_minutes = self.settings.OPS_OFFLINE_TIMEOUT_MINUTES
        data = parse_dat(state.dat)
        process_name = (
            self._normalize_process_name(data.get("pname")) or state.state_key or ""
        )

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
