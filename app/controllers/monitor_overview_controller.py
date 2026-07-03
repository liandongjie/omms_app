# -*- coding: utf-8 -*-
from fastapi import Depends

from app.controllers.base_controller import BaseController
from app.schemas.monitor_overview_schema import (
    MonitorOverviewCard,
    MonitorOverviewOsItem,
    MonitorOverviewTotalResponse,
)
from app.services.ops_service import ABNORMAL_STATUSES, OpsService, get_ops_service


def normalize_mentor_group(group: str | None) -> str | None:
    if group is None:
        return None
    normalized = group.strip()
    if not normalized or normalized.lower() == "all":
        return None
    return normalized


def parse_mentor_only_error(only_error: int | bool | None) -> bool:
    return int(only_error or 0) == 1


class MonitorOverviewController(BaseController):
    def __init__(self, ops_service: OpsService):
        self.ops_service = ops_service

    def get_total(self, group: str | None = "all", only_error: int = 0) -> MonitorOverviewTotalResponse:
        overview = self.ops_service.get_overview(
            group=normalize_mentor_group(group),
            only_error=parse_mentor_only_error(only_error),
        )
        return MonitorOverviewTotalResponse(
            os=MonitorOverviewCard(total=overview.os.total, alarm=overview.os.alarm_count),
            process=MonitorOverviewCard(total=overview.process.total, alarm=overview.process.alarm_count),
            log=MonitorOverviewCard(total=overview.log.total, alarm=overview.log.alarm_count),
        )

    def get_os_list(self, group: str | None = "all", only_error: int = 0) -> list[MonitorOverviewOsItem]:
        items = self.ops_service.get_os_states(
            group=normalize_mentor_group(group),
            only_error=parse_mentor_only_error(only_error),
        )
        return [
            MonitorOverviewOsItem(
                machine_tag=item.machine_tag,
                cpu_usage=item.cpu_usage,
                mem_usage=item.memory_usage,
                disk_usage=item.disk_usage,
                update_time=item.update_time,
                is_offline=1 if item.status == "offline" else 0,
                is_alarm=1 if item.status in ABNORMAL_STATUSES else 0,
            )
            for item in items
        ]


def get_monitor_overview_controller(
    ops_service: OpsService = Depends(get_ops_service),
) -> MonitorOverviewController:
    return MonitorOverviewController(ops_service)
