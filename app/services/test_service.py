# -*- coding: utf-8 -*-
# author: zc
# datetime: 2025/11/30 15:43
from app.services.base_service import BaseService
from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Type

from app.models.testModel import TestModel
from app.utils.db import get_db


class TestService(BaseService):
    """
    账户配置服务类
    """

    def qry_list(self) -> list[Type[TestModel]]:
        """
        查询账户配置列表
        """
        try:
            data_list = self.db.query(TestModel).all()
            return data_list
        except Exception as e:
            raise e


def get_test_service(db: Session = Depends(get_db)) -> TestService:
    return TestService(db)
