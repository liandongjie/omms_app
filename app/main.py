from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
import contextlib

from app.routes import monitor_overview_route, ops_route, test_route

from app.utils.db import get_db


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
app.include_router(ops_route.router, prefix="/api/ops", tags=["ops"])
app.include_router(monitor_overview_route.router, tags=["monitor-overview"])
