# -*- coding: utf-8 -*-
# author: zc
# datetime: 2025/11/29 22:32
from fastapi import APIRouter, Depends

from app.controllers.test_controller import TestController, get_test_controller
from app.schemas.common import ResponseModel

router = APIRouter()


@router.post("/list", response_model=ResponseModel)
def get_list(test_controller: TestController = Depends(get_test_controller)):
    """
    获取账户概览
    """
    dict_data_list = test_controller.get_list()
    return ResponseModel(data=dict_data_list, msg='SUCCESS')
