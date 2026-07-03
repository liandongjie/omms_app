# -*- coding: utf-8 -*-
from fastapi import Depends

from app.controllers.base_controller import BaseController
from app.schemas.ops_schema import AlarmItem, GroupItem, LogPageResponse, OsStateItem, OverviewResponse, ProcessStateItem
from app.services.ops_service import OpsService, get_ops_service


class OpsController(BaseController):
    def __init__(self, ops_service: OpsService):
        self.ops_service = ops_service

    def get_overview(self, group: str | None = None, only_error: bool = False, date: str | None = None) -> OverviewResponse:
        return self.ops_service.get_overview(group=group, only_error=only_error, date=date)

    def get_os_states(self, group: str | None = None, only_error: bool = False, date: str | None = None) -> list[OsStateItem]:
        return self.ops_service.get_os_states(group=group, only_error=only_error, date=date)

    def get_process_states(self, group: str | None = None, only_error: bool = False, date: str | None = None) -> list[ProcessStateItem]:
        return self.ops_service.get_process_states(group=group, only_error=only_error, date=date)

    def get_logs(
        self,
        group: str | None = None,
        machine_tag: str | None = None,
        level: str | None = None,
        date: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> LogPageResponse:
        return self.ops_service.get_logs(
            group=group,
            machine_tag=machine_tag,
            level=level,
            date=date,
            page=page,
            page_size=page_size,
        )

    def get_alarms(self, group: str | None = None, date: str | None = None) -> list[AlarmItem]:
        return self.ops_service.get_alarms(group=group, date=date)

    def get_groups(self) -> list[GroupItem]:
        return self.ops_service.get_groups()


def get_ops_controller(ops_service: OpsService = Depends(get_ops_service)) -> OpsController:
    return OpsController(ops_service)
