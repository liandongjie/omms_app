import logging

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import contextlib

from app.routes import monitor_overview_route, test_route
from app.schemas.common import ErrorDetail, ErrorResponseModel

from app.utils.db import get_db

logger = logging.getLogger(__name__)


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


# 创建 FastAPI 应用实例
app = FastAPI(
    title="omms_app",
    description="运营维护应用",
    default_response_class=Utf8JSONResponse,
    # version=get_settings().VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    redoc_ui_parameters={
        "cdn_url": "https://cdn.jsdelivr.net/npm/redoc@2.0.0-rc.50/bundles/redoc.standalone.js",
        "max_displayed_enum_values": 10,
        "required_props_first": True
    },
)


# 所有未捕获异常统一转换为 envelope；参数校验错误保留字段级明细。
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

# 创建 MQ 控制器实例（自动启动订阅）
mq_controller = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event handler - initialize MQ controller
    global mq_controller
    # 使用依赖注入获取RebuildLogService实例
    db_gen = get_db()
    db = next(db_gen)
    try:
        # mq_controller = MQController()
        pass
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
    yield
    # Shutdown event handler - stop MQ subscription
    if mq_controller:
        mq_controller.shutdown()
        print("MQ 订阅已停止")


# Set the lifespan context manager
app.router.lifespan_context = lifespan

# 包含路由
app.include_router(test_route.router, prefix="/api_test", tags=["test"])
app.include_router(monitor_overview_route.router, tags=["monitor-overview"])
