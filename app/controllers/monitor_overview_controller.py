# -*- coding: utf-8 -*-
from fastapi import Depends

from app.config import get_settings
from app.controllers.base_controller import BaseController
from app.schemas.monitor_overview_schema import (
    MonitorOverviewCard,
    MonitorOverviewOsItem,
    MonitorOverviewOsListRequest,
    MonitorOverviewOsListResponse,
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


def normalize_monitor_group(group: str | None) -> str | None:
    if group is None:
        return None
    normalized = group.strip()
    if not normalized or normalized.lower() == "all":
        return None
    return normalized


class MonitorOverviewController(BaseController):
    def __init__(self, ops_service: OpsService, settings=None):
        self.ops_service = ops_service
        self.settings = settings or getattr(ops_service, "settings", None) or get_settings()

    def get_total(self) -> MonitorOverviewTotalResponse:
        overview = self.ops_service.get_overview()
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

    def get_os_list(self, request: MonitorOverviewOsListRequest | None = None) -> MonitorOverviewOsListResponse:
        request = request or MonitorOverviewOsListRequest()
        page_no = self._normalize_page_no(request.page_no)
        page_size = self._normalize_page_size(request.page_size)
        group = normalize_monitor_group(request.group)

        items = [
            self._to_monitor_os_item(item)
            for item in self.ops_service.get_os_states(group=group)
        ]
        items = self._sort_os_items(items, request.sort_by or "", request.sort_order or "")

        total = len(items)
        start = (page_no - 1) * page_size
        end = start + page_size
        return MonitorOverviewOsListResponse(
            page_no=page_no,
            page_size=page_size,
            total=total,
            details=items[start:end],
        )

    def _normalize_page_no(self, page_no: int | None) -> int:
        default_page_no = self.settings.OPS_DEFAULT_PAGE_NO
        return max(int(page_no or default_page_no), 1)

    def _normalize_page_size(self, page_size: int | None) -> int:
        default_page_size = self.settings.OPS_DEFAULT_PAGE_SIZE
        max_page_size = self.settings.OPS_MAX_PAGE_SIZE
        return min(max(int(page_size or default_page_size), 1), max_page_size)

    @staticmethod
    def _to_monitor_os_item(item) -> MonitorOverviewOsItem:
        return MonitorOverviewOsItem(
            machine_tag=item.machine_tag,
            cpu_usage=item.cpu_usage,
            mem_usage=item.memory_usage,
            disk_usage=item.disk_usage,
            update_time=item.update_time,
            is_offline=1 if item.status == "offline" else 0,
            is_alarm=1 if item.status in ABNORMAL_STATUSES else 0,
        )

    @staticmethod
    def _sort_os_items(
        items: list[MonitorOverviewOsItem],
        sort_by: str,
        sort_order: str,
    ) -> list[MonitorOverviewOsItem]:
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


def get_monitor_overview_controller(
    ops_service: OpsService = Depends(get_ops_service),
) -> MonitorOverviewController:
    return MonitorOverviewController(ops_service)
