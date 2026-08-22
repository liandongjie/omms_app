# -*- coding: utf-8 -*-
import asyncio
import contextlib
import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.routes import monitor_overview_route, test_route, ws_route
from app.services.mq_consumer import MQConsumer
from app.services.ws_manager import broadcast_loop
from app.schemas.common import ErrorDetail, ErrorResponseModel
from app.utils.db import check_database_connection

logger = logging.getLogger(__name__)


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


# 创建 FastAPI 应用实例
app = FastAPI(
    title="omms_app",
    description="运营维护应用",
    default_response_class=Utf8JSONResponse,
    docs_url="/docs",
    redoc_url="/redoc",
    redoc_ui_parameters={
        "cdn_url": "https://cdn.jsdelivr.net/npm/redoc@2.0.0-rc.50/bundles/redoc.standalone.js",
        "max_displayed_enum_values": 10,
        "required_props_first": True
    },
)


# ---------- 统一异常处理 ----------
# 所有未捕获异常统一转换为 {code, msg, data/errors} 响应，避免把堆栈或
# FastAPI 默认错误体直接暴露给前端；参数校验错误附带字段级明细。


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        logger.error(
            "server HTTP exception on %s %s: %s",
            request.method,
            request.url.path,
            exc.detail,
        )
        msg = "internal server error"
    else:
        msg = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponseModel(code=exc.status_code, msg=msg).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        ErrorDetail(
            field=".".join(str(part) for part in err.get("loc", [])),
            message=str(err.get("msg", "")),
        )
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorResponseModel(
            code=422, msg="request validation failed", errors=errors
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        # 未知异常详情只进入服务器日志，响应不得泄漏 SQL、凭据或调用栈。
        content=ErrorResponseModel(code=500, msg="internal server error").model_dump(),
    )


# ---------- 请求日志中间件 ----------
# 记录 method / path / status / duration，作为性能基线和问题定位的统一来源。
class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # WebSocket 等非 HTTP 连接不经过耗时统计，直接透传
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status_holder = {}

        async def send_with_status(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "request method=%s path=%s status=%s duration_ms=%.1f",
                scope.get("method"),
                scope.get("path"),
                status_holder.get("status", "-"),
                duration_ms,
            )


app.add_middleware(RequestLoggingMiddleware)


# MQ 消费端实例：RabbitMQ 不可用时由后台线程循环重试，不阻塞应用启动
mq_consumer = MQConsumer()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动前主动探测数据库：连不上立即终止启动，避免“进程活着但数据全空”的假性可用。
    try:
        check_database_connection()
    except SQLAlchemyError as exc:
        logger.error("数据库连接探测失败，应用启动终止: %s", exc, exc_info=True)
        raise RuntimeError(f"database unavailable: {exc}") from exc

    # 非测试环境启动 MQ 消费端与实时推送；两者不可用时都由内部循环重试/降级，
    # 不阻塞应用启动。
    settings = get_settings()
    broadcast_task = None
    if settings.environment != "testing":
        mq_consumer.start()
        broadcast_task = asyncio.create_task(broadcast_loop())

    yield

    if settings.environment != "testing":
        if mq_consumer.is_running():
            mq_consumer.shutdown()
            logger.info("MQ 消费端已停止")
        if broadcast_task is not None:
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass
            logger.info("实时推送广播任务已停止")


app.router.lifespan_context = lifespan


# ---------- 系统端点 ----------
@app.get("/health", tags=["system"])
def health_check():
    """服务健康检查：数据库可连接时返回 200，否则返回 503。"""
    try:
        check_database_connection()
        database = "up"
        status_code = 200
    except SQLAlchemyError as exc:
        logger.error("health check database failure: %s", exc)
        database = "down"
        status_code = 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if database == "up" else "degraded", "database": database},
    )


# 包含路由
app.include_router(test_route.router, prefix="/api_test", tags=["test"])
app.include_router(monitor_overview_route.router, tags=["monitor-overview"])
app.include_router(ws_route.router, tags=["websocket"])
