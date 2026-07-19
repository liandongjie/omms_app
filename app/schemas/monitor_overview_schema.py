# -*- coding: utf-8 -*-
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


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
MonitorOverviewProcessSortBy = Literal[
    "",
    "machine_tag",
    "process_name",
    "pid",
    "cpu",
    "mem",
    "update_time",
    "is_offline",
    "is_alarm",
]
MonitorOverviewLogSortBy = Literal[
    "",
    "log_id",
    "date",
    "machine_tag",
    "log_name",
    "level",
    "update_time",
]


class MonitorOverviewCard(BaseModel):
    total: int = 0
    alarm: int = 0
    error: int = 0


class MonitorOverviewTotalResponse(BaseModel):
    os: MonitorOverviewCard
    process: MonitorOverviewCard
    log: MonitorOverviewCard


class MonitorOverviewGroupItem(BaseModel):
    group: str
    display_name: str


class MonitorOverviewGroupListResponse(BaseModel):
    details: list[MonitorOverviewGroupItem]


class MonitorOverviewOsItem(BaseModel):
    machine_tag: str
    group: str | None = None
    cpu_usage: float | None = None
    mem_usage: float | None = None
    disk_usage: float | None = None
    disk_home_usage: float | None = None
    cpu_alarm: int = 0
    mem_alarm: int = 0
    disk_alarm: int = 0
    disk_home_alarm: int = 0
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


class MonitorOverviewProcessItem(BaseModel):
    machine_tag: str
    group: str | None = None
    process_name: str
    args: str | None = None
    pid: int | None = None
    cpu: float | None = None
    mem: float | None = None
    update_time: str | None = None
    is_configured: bool = True
    is_offline: int = 0
    is_alarm: int = 0
    extra: dict[str, Any] | None = None


class MonitorOverviewProcessListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str | None = ""
    page_no: int | None = None
    page_size: int | None = None
    sort_by: MonitorOverviewProcessSortBy | None = ""
    sort_order: MonitorOverviewSortOrder | None = ""


class MonitorOverviewProcessListResponse(BaseModel):
    page_no: int
    page_size: int
    total: int
    details: list[MonitorOverviewProcessItem]


class MonitorOverviewLogItem(BaseModel):
    log_id: int
    date: str | None = None
    machine_tag: str | None = None
    log_name: str | None = None
    level: str | None = None
    log: str | None = None
    update_time: str | None = None
    is_alarm: int = 0


class MonitorOverviewLogListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str | None = ""
    machine_tag: str | None = None
    only_error: bool | int | None = 0
    level: str | None = ""
    date: str | None = ""
    page_no: int | None = None
    page_size: int | None = None
    sort_by: MonitorOverviewLogSortBy | None = ""
    sort_order: MonitorOverviewSortOrder | None = ""

    @field_validator("level")
    @classmethod
    def normalize_level(cls, value: str | None) -> str:
        if value is None:
            return ""
        normalized = value.strip().lower()
        if normalized not in {"", "info", "warn", "error"}:
            raise ValueError("unsupported level")
        return normalized


class MonitorOverviewLogListResponse(BaseModel):
    page_no: int
    page_size: int
    total: int
    details: list[MonitorOverviewLogItem]
