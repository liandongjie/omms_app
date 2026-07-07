# -*- coding: utf-8 -*-
import traceback

from fastapi import APIRouter, Body, Depends

from app.controllers.monitor_overview_controller import (
    MonitorOverviewController,
    get_monitor_overview_controller,
)
from app.schemas.common import ErrorResponseModel, ResponseModel
from app.schemas.monitor_overview_schema import MonitorOverviewOsListRequest

router = APIRouter()


@router.get("/api_omms/monitor/overview/total", response_model=ResponseModel)
def get_monitor_overview_total(
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    try:
        return ResponseModel(data=controller.get_total(), msg="success")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))


@router.post("/api_omms/monitor/overview/os/list", response_model=ResponseModel)
def post_monitor_overview_os_list(
    request: MonitorOverviewOsListRequest | None = Body(default=None),
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    try:
        return ResponseModel(data=controller.get_os_list(request), msg="success")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))
