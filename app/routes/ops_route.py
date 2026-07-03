# -*- coding: utf-8 -*-
import traceback
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.controllers.ops_controller import OpsController, get_ops_controller
from app.schemas.common import ErrorResponseModel, ResponseModel

router = APIRouter()


@router.get("/overview", response_model=ResponseModel)
def get_overview(
    group: str | None = None,
    only_error: bool = False,
    date: str | None = None,
    ops_controller: OpsController = Depends(get_ops_controller),
):
    try:
        data = ops_controller.get_overview(group=group, only_error=only_error, date=date)
        return ResponseModel(data=data, msg="SUCCESS")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))


@router.get("/os-states", response_model=ResponseModel)
def get_os_states(
    group: str | None = None,
    only_error: bool = False,
    date: str | None = None,
    ops_controller: OpsController = Depends(get_ops_controller),
):
    try:
        data = ops_controller.get_os_states(group=group, only_error=only_error, date=date)
        return ResponseModel(data=data, msg="SUCCESS")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))


@router.get("/process-states", response_model=ResponseModel)
def get_process_states(
    group: str | None = None,
    only_error: bool = False,
    date: str | None = None,
    ops_controller: OpsController = Depends(get_ops_controller),
):
    try:
        data = ops_controller.get_process_states(group=group, only_error=only_error, date=date)
        return ResponseModel(data=data, msg="SUCCESS")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))


@router.get("/logs", response_model=ResponseModel)
def get_logs(
    group: str | None = None,
    machine_tag: str | None = None,
    level: Literal["info", "warn", "error"] | None = None,
    date: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    ops_controller: OpsController = Depends(get_ops_controller),
):
    try:
        data = ops_controller.get_logs(
            group=group,
            machine_tag=machine_tag,
            level=level,
            date=date,
            page=page,
            page_size=page_size,
        )
        return ResponseModel(data=data, msg="SUCCESS")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))


@router.get("/alarms", response_model=ResponseModel)
def get_alarms(
    group: str | None = None,
    date: str | None = None,
    ops_controller: OpsController = Depends(get_ops_controller),
):
    try:
        data = ops_controller.get_alarms(group=group, date=date)
        return ResponseModel(data=data, msg="SUCCESS")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))


@router.get("/groups", response_model=ResponseModel)
def get_groups(ops_controller: OpsController = Depends(get_ops_controller)):
    try:
        return ResponseModel(data=ops_controller.get_groups(), msg="SUCCESS")
    except Exception as e:
        traceback.print_exc()
        return ErrorResponseModel(msg=str(e))
