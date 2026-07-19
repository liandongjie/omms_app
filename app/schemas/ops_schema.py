# -*- coding: utf-8 -*-
from typing import Any

from pydantic import BaseModel, Field


class OverviewOsStats(BaseModel):
    total: int = 0
    monitor_items: int = 0
    abnormal_count: int = 0
    alarm_count: int = 0


class OverviewProcessStats(BaseModel):
    total: int = 0
    running_count: int = 0
    abnormal_count: int = 0
    alarm_count: int = 0


class OverviewLogStats(BaseModel):
    total: int = 0
    error_count: int = 0
    warn_count: int = 0
    alarm_count: int = 0


class OverviewResponse(BaseModel):
    os: OverviewOsStats = Field(default_factory=OverviewOsStats)
    process: OverviewProcessStats = Field(default_factory=OverviewProcessStats)
    log: OverviewLogStats = Field(default_factory=OverviewLogStats)


class OsStateItem(BaseModel):
    machine_tag: str
    group: str | None = None
    cpu_usage: float | None = None
    memory_usage: float | None = None
    disk_usage: float | None = None
    disk_home_usage: float | None = None
    cpu_alarm: int = 0
    mem_alarm: int = 0
    disk_alarm: int = 0
    disk_home_alarm: int = 0
    status: str
    message: str
    update_time: str | None = None


class ProcessStateItem(BaseModel):
    machine_tag: str
    group: str | None = None
    process_name: str
    args: str | None = None
    pid: int | None = None
    cpu: float | None = None
    memory: float | None = None
    is_configured: bool = True
    status: str
    message: str
    update_time: str | None = None
    extra: dict[str, Any] | None = None


class LogItem(BaseModel):
    log_id: int
    date: str | None = None
    machine_tag: str | None = None
    group: str | None = None
    log_name: str | None = None
    level: str | None = None
    log: str | None = None
    update_time: str | None = None


class LogPageResponse(BaseModel):
    items: list[LogItem]
    total: int
    page: int
    page_size: int


class AlarmItem(BaseModel):
    type: str
    level: str
    machine_tag: str | None = None
    group: str | None = None
    target: str | None = None
    message: str
    update_time: str | None = None


class GroupItem(BaseModel):
    group: str
    display_name: str
