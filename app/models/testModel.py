# -*- coding: utf-8 -*-
# author: zc
# datetime: 2025/11/29 23:53
from sqlalchemy import Column, String, Double, Integer

from app.models.database import Base


class TestModel(Base):
    """测试数据库"""
    __tablename__ = "test_db"

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    name = Column(String(32), nullable=True, comment="名称")
