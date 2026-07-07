# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import BaseModel, ConfigDict


MonitorOverviewSortBy = Literal[
    "",
    "machine_tag",
    "cpu_usage",
    "mem_usage",
    "disk_usage",
    "update_time",
    "is_offline",
    "is_alarm",
]
MonitorOverviewSortOrder = Literal["", "asc", "desc"]


class MonitorOverviewCard(BaseModel):
    total: int = 0
    alarm: int = 0
    error: int = 0


class MonitorOverviewTotalResponse(BaseModel):
    os: MonitorOverviewCard
    process: MonitorOverviewCard
    log: MonitorOverviewCard


class MonitorOverviewOsItem(BaseModel):
    machine_tag: str
    cpu_usage: float | None = None
    mem_usage: float | None = None
    disk_usage: float | None = None
    update_time: str | None = None
    is_offline: int = 0
    is_alarm: int = 0


class MonitorOverviewOsListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str | None = ""
    page_no: int | None = None
    page_size: int | None = None
    sort_by: MonitorOverviewSortBy | None = ""
    sort_order: MonitorOverviewSortOrder | None = ""


class MonitorOverviewOsListResponse(BaseModel):
    page_no: int
    page_size: int
    total: int
    details: list[MonitorOverviewOsItem]
