# -*- coding: utf-8 -*-
# author: zc
# datetime: 2025/11/28 23:36

from abc import ABC

from sqlalchemy.orm import Session


class BaseService(ABC):
    """服务基类：整合数据库会话和数据访问抽象接口"""
    def __init__(self, db: Session):
        self.db = db  # 数据库会话（由依赖注入提供）