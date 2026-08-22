# -*- coding: utf-8 -*-
"""WebSocket 实时推送管理。

把“数据有变更就通知前端刷新”的广播机制集中在这里：
- ConnectionManager 维护在线连接集合；
- 变更检测器周期性用轻量聚合查询（MAX 日志 id / MAX 状态时间 / 状态条数）
  判断数据是否变化，比每个用户每 5 秒轮询便宜得多；
- 检测到变化后向所有在线连接广播 ``refresh`` 事件，前端收到后复用现有加载逻辑；
- 前端断线时自动回退到 5 秒轮询，广播异常不影响服务可用性。
"""
import asyncio
import logging
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy import func

from app.models.ops_model import OpsLog, OpsState
from app.utils.cache import invalidate_monitor_cache
from app.utils.db import SessionLocal
from app.utils.ops_parse import today_yyyymmdd

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 2


class ConnectionManager:
    """维护在线 WebSocket 连接并广播事件。"""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        """向所有在线连接发送 JSON；发送失败的连接视为已断开并清理。"""
        stale = []
        for connection in list(self._connections):
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


async def broadcast_refresh() -> None:
    """广播前再次失效缓存，封住 DB version 检测与 consumer 失效之间的竞态。"""
    invalidate_monitor_cache()
    await manager.broadcast(
        {
            "event": "refresh",
            "at": datetime.now().isoformat(timespec="seconds"),
        }
    )


def fetch_data_version(db) -> tuple:
    """轻量变更检测签名。

    返回 (最大日志 id, 日志最新时间, 状态最新时间, 状态条数)，任一变化
    都视为监控数据有更新。均为索引/主键上的聚合查询，代价远低于逐用户轮询。
    """
    today = today_yyyymmdd()
    log_row = (
        db.query(func.max(OpsLog.log_id), func.max(OpsLog.update_time))
        .filter(OpsLog.date == today)
        .one()
    )
    state_row = (
        db.query(func.max(OpsState.update_time), func.count(OpsState.date))
        .filter(OpsState.date == today)
        .one()
    )
    return (log_row[0], log_row[1], state_row[0], state_row[1])


async def broadcast_loop(
    interval_seconds: int = REFRESH_INTERVAL_SECONDS,
) -> None:
    """后台周期任务：检测到数据变化即广播 refresh 事件。"""
    last_version = None
    while True:
        try:
            db = SessionLocal()
            try:
                version = fetch_data_version(db)
            finally:
                db.close()
            if last_version is not None and version != last_version:
                await broadcast_refresh()
            last_version = version
        except Exception as exc:  # noqa: BLE001 - 广播失败不能拖垮服务
            logger.warning("实时变更检测失败: %s", exc)
        await asyncio.sleep(interval_seconds)
