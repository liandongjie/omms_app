# -*- coding: utf-8 -*-
import traceback

from fastapi import APIRouter, Depends, Query

from app.controllers.monitor_overview_controller import (
    MonitorOverviewController,
    get_monitor_overview_controller,
)
from app.schemas.common import ErrorResponseModel, ResponseModel

router = APIRouter()


@router.get("/api_omms/monitor/overview/total", response_model=ResponseModel)
def get_monitor_overview_total(
    group: str = Query(default="all"),
    only_error: int = Query(default=0, ge=0, le=1),
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    try:
        return ResponseModel(data=controller.get_total(group=group, only_error=only_error), msg="success")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))


@router.get("/api_omms/monitor/overview/os/list", response_model=ResponseModel)
def get_monitor_overview_os_list(
    group: str = Query(default="all"),
    only_error: int = Query(default=0, ge=0, le=1),
    controller: MonitorOverviewController = Depends(get_monitor_overview_controller),
):
    try:
        return ResponseModel(data=controller.get_os_list(group=group, only_error=only_error), msg="success")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))
