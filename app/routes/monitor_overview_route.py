# -*- coding: utf-8 -*-
from fastapi import APIRouter, Body, Depends

from app.controllers.monitor_overview_controller import (
    MonitorOverviewController,
    get_monitor_overview_controller,
)
from app.schemas.common import ResponseModel
from app.schemas.monitor_overview_schema import (
    MonitorOverviewLogListRequest,
    MonitorOverviewOsListRequest,
    MonitorOverviewProcessListRequest,
)

router = APIRouter()


@router.get("/api_omms/monitor/overview/total", response_model=ResponseModel)
def get_monitor_overview_total(
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    return ResponseModel(data=controller.get_total(), msg="success")


@router.get("/api_omms/monitor/group/list", response_model=ResponseModel)
def get_monitor_group_list(
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    return ResponseModel(data=controller.get_group_list(), msg="success")


@router.post("/api_omms/monitor/overview/os/list", response_model=ResponseModel)
def post_monitor_overview_os_list(
    request: MonitorOverviewOsListRequest | None = Body(default=None),
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    return ResponseModel(data=controller.get_os_list(request), msg="success")


@router.post("/api_omms/monitor/overview/process/list", response_model=ResponseModel)
def post_monitor_overview_process_list(
    request: MonitorOverviewProcessListRequest | None = Body(default=None),
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    return ResponseModel(data=controller.get_process_list(request), msg="success")


@router.post("/api_omms/monitor/overview/log/list", response_model=ResponseModel)
def post_monitor_overview_log_list(
    request: MonitorOverviewLogListRequest | None = Body(default=None),
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    return ResponseModel(data=controller.get_log_list(request), msg="success")
