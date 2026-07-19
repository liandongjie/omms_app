# -*- coding: utf-8 -*-
from fastapi import Depends

from app.config import get_settings
from app.controllers.base_controller import BaseController
from app.schemas.monitor_overview_schema import (
    MonitorOverviewCard,
    MonitorOverviewGroupItem,
    MonitorOverviewGroupListResponse,
    MonitorOverviewLogItem,
    MonitorOverviewLogListRequest,
    MonitorOverviewLogListResponse,
    MonitorOverviewOsItem,
    MonitorOverviewOsListRequest,
    MonitorOverviewOsListResponse,
    MonitorOverviewProcessItem,
    MonitorOverviewProcessListRequest,
    MonitorOverviewProcessListResponse,
    MonitorOverviewTotalResponse,
)
from app.services.ops_service import ABNORMAL_STATUSES, OpsService, get_ops_service


OS_SORT_FIELDS = {
    "machine_tag",
    "cpu_usage",
    "mem_usage",
    "disk_usage",
    "update_time",
    "is_offline",
    "is_alarm",
}
PROCESS_SORT_FIELDS = {
    "machine_tag",
    "process_name",
    "pid",
    "cpu",
    "mem",
    "update_time",
    "is_offline",
    "is_alarm",
}
LOG_ALARM_LEVELS = {"warn", "error"}


def normalize_monitor_group(group: str | None) -> str | None:
    """归一化监控分组参数。

    Args:
        group: 原始分组名称。

    Returns:
        去除首尾空格后的分组名；空值、空字符串或 ``all`` 返回 None。
    """
    if group is None:
        return None
    normalized = group.strip()
    if not normalized or normalized.lower() == "all":
        return None
    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    """归一化可选文本参数。

    Args:
        value: 原始可选文本。

    Returns:
        去除首尾空格后的文本；缺失或空文本返回 None。
    """
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class MonitorOverviewController(BaseController):
    """把 ``OpsService`` 的领域结果转换为监控总览兼容接口的数据结构。

    OS、进程列表在服务返回完整结果后由本控制器排序和分页；日志保留服务层的
    数据库分页。转换过程中还会把领域状态统一映射为接口需要的告警/离线标记。
    """

    def __init__(self, ops_service: OpsService, settings=None):
        """初始化兼容接口控制器。

        Args:
            ops_service: 提供监控领域数据的服务实例。
            settings: 可选配置对象；未传入时优先复用服务配置。
        """
        self.ops_service = ops_service
        self.settings = settings or getattr(ops_service, "settings", None) or get_settings()

    def get_total(self) -> MonitorOverviewTotalResponse:
        """获取 OS、进程和日志的总览卡片数据。

        Returns:
            已转换为监控总览兼容结构的统计结果。
        """
        # 获取服务层统一口径的三类总览统计。
        overview = self.ops_service.get_overview()
        # 转换为兼容接口的卡片字段，其中 error 沿用各类型既定口径。
        return MonitorOverviewTotalResponse(
            os=MonitorOverviewCard(
                total=overview.os.total,
                alarm=overview.os.alarm_count,
                error=overview.os.alarm_count,
            ),
            process=MonitorOverviewCard(
                total=overview.process.total,
                alarm=overview.process.alarm_count,
                error=overview.process.alarm_count,
            ),
            log=MonitorOverviewCard(
                total=overview.log.total,
                alarm=overview.log.alarm_count,
                error=overview.log.error_count,
            ),
        )

    def get_group_list(self) -> MonitorOverviewGroupListResponse:
        """获取监控页面可用的分组列表。

        Returns:
            包含分组值和展示名称的兼容响应。
        """
        return MonitorOverviewGroupListResponse(
            details=[
                MonitorOverviewGroupItem(group=item.group, display_name=item.display_name)
                for item in self.ops_service.get_groups()
            ]
        )

    def get_os_list(self, request: MonitorOverviewOsListRequest | None = None) -> MonitorOverviewOsListResponse:
        """获取经过转换、排序和内存分页的 OS 状态列表。

        Args:
            request: OS 列表筛选、排序和分页参数；缺失时使用 schema 默认值。

        Returns:
            包含当前页 OS 状态和总数的兼容响应。

        Raises:
            ValueError: sort_by 不是受支持的 OS 排序字段时抛出。
        """
        # 补齐默认请求，并统一归一化分页和分组参数。
        request = request or MonitorOverviewOsListRequest()
        page_no = self._normalize_page_no(request.page_no)
        page_size = self._normalize_page_size(request.page_size)
        group = normalize_monitor_group(request.group)

        # OS 数据先完成领域状态判定，再转换、排序并按兼容接口的页码切片。
        items = [
            self._to_monitor_os_item(item)
            for item in self.ops_service.get_os_states(group=group)
        ]
        # 按请求字段排序；未指定字段时使用异常优先的默认顺序。
        items = self._sort_os_items(items, request.sort_by or "", request.sort_order or "")

        # 在转换和排序后的完整列表上计算总数，再截取当前页。
        total = len(items)
        start = (page_no - 1) * page_size
        end = start + page_size
        return MonitorOverviewOsListResponse(
            page_no=page_no,
            page_size=page_size,
            total=total,
            details=items[start:end],
        )

    def get_process_list(
        self,
        request: MonitorOverviewProcessListRequest | None = None,
    ) -> MonitorOverviewProcessListResponse:
        """获取经过转换、排序和内存分页的进程状态列表。

        Args:
            request: 进程列表筛选、排序和分页参数；缺失时使用 schema 默认值。

        Returns:
            包含当前页进程状态和总数的兼容响应。

        Raises:
            ValueError: sort_by 不是受支持的进程排序字段时抛出。
        """
        # 补齐默认请求，并统一归一化分页和分组参数。
        request = request or MonitorOverviewProcessListRequest()
        page_no = self._normalize_page_no(request.page_no)
        page_size = self._normalize_page_size(request.page_size)
        group = normalize_monitor_group(request.group)

        # 全部分组查询时同时保留没有配置项的 state-only 进程，避免兼容接口漏数据。
        items = [
            self._to_monitor_process_item(item)
            for item in self.ops_service.get_process_states(group=group, include_state_only=True)
        ]
        # 按请求字段排序；未指定字段时使用异常优先的默认顺序。
        items = self._sort_process_items(items, request.sort_by or "", request.sort_order or "")

        # 在转换和排序后的完整列表上计算总数，再截取当前页。
        total = len(items)
        start = (page_no - 1) * page_size
        end = start + page_size
        return MonitorOverviewProcessListResponse(
            page_no=page_no,
            page_size=page_size,
            total=total,
            details=items[start:end],
        )

    def get_log_list(
        self,
        request: MonitorOverviewLogListRequest | None = None,
    ) -> MonitorOverviewLogListResponse:
        """获取由服务层完成筛选、排序和分页的日志列表。

        Args:
            request: 日志筛选、排序和分页参数；缺失时使用 schema 默认值。

        Returns:
            包含当前页日志和分页元数据的兼容响应。

        Raises:
            ValueError: sort_by 不是服务层支持的日志排序字段时抛出。
        """
        # 补齐默认请求，并统一归一化分页、分组和日期参数。
        request = request or MonitorOverviewLogListRequest()
        page_no = self._normalize_page_no(request.page_no)
        page_size = self._normalize_page_size(request.page_size)
        group = normalize_monitor_group(request.group)
        date = normalize_optional_text(request.date)

        # 日志筛选、排序和分页由服务层直接完成。
        page = self.ops_service.get_logs(
            group=group,
            machine_tag=request.machine_tag,
            level=request.level or None,
            date=date,
            page=page_no,
            page_size=page_size,
            only_error=bool(request.only_error),
            sort_by=request.sort_by or "",
            sort_order=request.sort_order or "",
        )
        # 保留服务层分页元数据，仅转换当前页的日志条目。
        return MonitorOverviewLogListResponse(
            page_no=page.page,
            page_size=page.page_size,
            total=page.total,
            details=[self._to_monitor_log_item(item) for item in page.items],
        )

    def _normalize_page_no(self, page_no: int | None) -> int:
        """把页码限制为不小于 1 的整数。

        Args:
            page_no: 请求页码，缺失时使用配置默认值。

        Returns:
            归一化后的页码。
        """
        default_page_no = self.settings.OPS_DEFAULT_PAGE_NO
        return max(int(page_no or default_page_no), 1)

    def _normalize_page_size(self, page_size: int | None) -> int:
        """把每页数量限制在配置允许的范围内。

        Args:
            page_size: 请求的每页数量，缺失时使用配置默认值。

        Returns:
            介于 1 和最大页尺寸之间的数量。
        """
        # 统一限制分页边界，避免不同列表接口各自处理默认值和超大页尺寸。
        default_page_size = self.settings.OPS_DEFAULT_PAGE_SIZE
        max_page_size = self.settings.OPS_MAX_PAGE_SIZE
        return min(max(int(page_size or default_page_size), 1), max_page_size)

    @staticmethod
    def _to_monitor_os_item(item) -> MonitorOverviewOsItem:
        """把领域 OS 状态转换为兼容接口条目。

        Args:
            item: 服务层返回的 OS 状态项。

        Returns:
            使用数值告警和离线标记的兼容条目。
        """
        # 对外接口只暴露布尔语义的数值标记，具体状态文本仍由服务层负责判定。
        return MonitorOverviewOsItem(
            machine_tag=item.machine_tag,
            group=item.group,
            cpu_usage=item.cpu_usage,
            mem_usage=item.memory_usage,
            disk_usage=item.disk_usage,
            disk_home_usage=item.disk_home_usage,
            cpu_alarm=item.cpu_alarm,
            mem_alarm=item.mem_alarm,
            disk_alarm=item.disk_alarm,
            disk_home_alarm=item.disk_home_alarm,
            update_time=item.update_time,
            is_offline=1 if item.status == "offline" else 0,
            is_alarm=1 if item.status in ABNORMAL_STATUSES else 0,
        )

    @staticmethod
    def _to_monitor_process_item(item) -> MonitorOverviewProcessItem:
        """把领域进程状态转换为兼容接口条目。

        Args:
            item: 服务层返回的进程状态项。

        Returns:
            包含配置标记、运行指标和异常标记的兼容条目。
        """
        return MonitorOverviewProcessItem(
            machine_tag=item.machine_tag,
            group=item.group,
            process_name=item.process_name,
            args=item.args,
            pid=item.pid,
            cpu=item.cpu,
            mem=item.memory,
            update_time=item.update_time,
            is_configured=item.is_configured,
            is_offline=1 if item.status == "offline" else 0,
            is_alarm=1 if item.status in ABNORMAL_STATUSES else 0,
            extra=item.extra,
        )

    @staticmethod
    def _to_monitor_log_item(item) -> MonitorOverviewLogItem:
        """把领域日志转换为兼容接口条目。

        Args:
            item: 服务层返回的日志项。

        Returns:
            日志级别已归一化并带告警标记的兼容条目。
        """
        level = (item.level or "").lower()
        return MonitorOverviewLogItem(
            log_id=item.log_id,
            date=item.date,
            machine_tag=item.machine_tag,
            log_name=item.log_name,
            level=level,
            log=item.log,
            update_time=item.update_time,
            is_alarm=1 if level in LOG_ALARM_LEVELS else 0,
        )

    @staticmethod
    def _sort_os_items(
        items: list[MonitorOverviewOsItem],
        sort_by: str,
        sort_order: str,
    ) -> list[MonitorOverviewOsItem]:
        """按照默认优先级或指定字段排序 OS 条目。

        Args:
            items: 待排序的 OS 条目。
            sort_by: 排序字段；为空时使用告警优先的默认顺序。
            sort_order: ``desc`` 表示降序，其他值按升序处理。

        Returns:
            新的已排序列表。

        Raises:
            ValueError: sort_by 不在 OS 排序字段白名单中时抛出。
        """
        # 未指定排序时优先展示告警、离线项，再按机器标签稳定排序。
        if not sort_by:
            return sorted(items, key=lambda item: (-item.is_alarm, -item.is_offline, item.machine_tag))

        if sort_by not in OS_SORT_FIELDS:
            raise ValueError(f"unsupported sort_by: {sort_by}")

        reverse = sort_order == "desc"
        return sorted(
            items,
            key=lambda item: (getattr(item, sort_by) is None, getattr(item, sort_by)),
            reverse=reverse,
        )

    @staticmethod
    def _sort_process_items(
        items: list[MonitorOverviewProcessItem],
        sort_by: str,
        sort_order: str,
    ) -> list[MonitorOverviewProcessItem]:
        """按照默认优先级或指定字段排序进程条目。

        Args:
            items: 待排序的进程条目。
            sort_by: 排序字段；为空时使用告警优先的默认顺序。
            sort_order: ``desc`` 表示降序，其他值按升序处理。

        Returns:
            新的已排序列表。

        Raises:
            ValueError: sort_by 不在进程排序字段白名单中时抛出。
        """
        # 默认顺序与 OS 一致，并追加进程名以稳定同一机器下的结果顺序。
        if not sort_by:
            return sorted(
                items,
                key=lambda item: (-item.is_alarm, -item.is_offline, item.machine_tag, item.process_name),
            )

        if sort_by not in PROCESS_SORT_FIELDS:
            raise ValueError(f"unsupported sort_by: {sort_by}")

        reverse = sort_order == "desc"
        return sorted(
            items,
            key=lambda item: (getattr(item, sort_by) is None, getattr(item, sort_by)),
            reverse=reverse,
        )


def get_monitor_overview_controller(
    ops_service: OpsService = Depends(get_ops_service),
) -> MonitorOverviewController:
    """构造供 FastAPI 依赖注入使用的监控总览控制器。

    Args:
        ops_service: 由依赖注入提供的运维服务。

    Returns:
        绑定该服务的监控总览控制器。
    """
    return MonitorOverviewController(ops_service)
