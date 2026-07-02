# -*- coding:utf-8 -*-
# author: zc
# datetime: 2025/9/13 18:17

from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, List

# 泛型类型变量
T = TypeVar('T')


class ResponseModel(BaseModel, Generic[T]):
    """通用成功响应模型"""
    code: int = 200
    msg: Optional[str] = None
    data: Optional[T] = None


class ErrorDetail(BaseModel):
    """错误详情模型（参数校验等场景）"""
    field: str  # 错误字段
    message: str  # 错误描述


class ErrorResponseModel(BaseModel, Generic[T]):
    """通用错误响应模型"""
    code: int = 500
    msg: Optional[str] = None
    errors: Optional[List[ErrorDetail]] = None
