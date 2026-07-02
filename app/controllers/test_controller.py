# -*- coding: utf-8 -*-
# author: zc
# datetime: 2025/11/28 21:47
import datetime
import numpy as np
import pandas as pd
import traceback
from fastapi import Depends

from app.controllers.base_controller import BaseController
from app.services.test_service import TestService, get_test_service


class TestController(BaseController):
    """账户概览 控制器"""

    def __init__(self, test_service: TestService):
        self.test_service = test_service


    def get_list(self) -> list[dict]:
        try:
            data_list = self.test_service.qry_list()
            new_list = []
            for item in data_list:
                new_list.append({'id': item.id, 'name': item.name})

            return new_list
        except Exception as e:
            raise e


def get_test_controller(test_service: TestService = Depends(get_test_service)) -> TestController:
    return TestController(test_service)
