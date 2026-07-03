# -*- coding: utf-8 -*-
from pydantic import BaseModel


class MonitorOverviewCard(BaseModel):
    total: int = 0
    alarm: int = 0


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
