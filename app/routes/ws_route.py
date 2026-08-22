# -*- coding: utf-8 -*-
"""WebSocket 监控实时推送端点。"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/monitor")
async def monitor_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # 连接成功后先发 hello，前端以此确认 WS 可用并切换为事件驱动刷新
        await websocket.send_json({"event": "hello"})
        while True:
            # 客户端心跳 ping；收到即回 pong，用于探测连接活性
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
