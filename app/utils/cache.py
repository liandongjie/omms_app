# -*- coding: utf-8 -*-
"""Redis 缓存工具层。

为监控页面 5 秒轮询提供旁路缓存，降低 MySQL 重复查询压力（total 与列表
每轮都在重复计算同一份领域结果）。设计要点：

- 缓存不可用时自动降级为直查数据库，且周期性重试恢复，不允许缓存故障拖垮业务；
- 测试环境（ENVIRONMENT=testing）直接禁用缓存，单测全部走真实计算路径；
- 过期时间由业务方传入（默认见 OPS_CACHE_TTL_SECONDS，3 秒 < 前端 5 秒轮询）。
"""
import logging
import time

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_RETRY_INTERVAL_SECONDS = 30

_client: "redis.Redis | None" = None
_client_environment: str | None = None
_retry_after: float = 0.0

_MONITOR_CACHE_PATTERNS = {
    "state": ("omms:os:*", "omms:process:*"),
    "log": ("omms:log_stats:*",),
}


def _new_client(settings) -> "redis.Redis | None":
    """创建并探测 Redis 连接；失败返回 None。"""
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return client
    except Exception as exc:  # noqa: BLE001 - 缓存故障不允许影响业务
        logger.warning("Redis 不可用，缓存降级为直查数据库（%s）", exc)
        return None


def get_redis_client():
    """返回可用 Redis 客户端；不可用时返回 None，并每 30 秒重试一次连接。"""
    global _client, _client_environment, _retry_after
    settings = get_settings()
    if settings.environment == "testing":
        # 测试环境不连接 Redis，保证单测与 CI 无外部依赖
        return None

    now = time.monotonic()
    if _client is not None and _client_environment == settings.environment:
        return _client
    if now < _retry_after:
        return None

    candidate = _new_client(settings)
    if candidate is None:
        _client = None
        _retry_after = now + _RETRY_INTERVAL_SECONDS
        return None
    _client = candidate
    _client_environment = settings.environment
    return _client


def cache_get(key: str) -> str | None:
    """读取缓存；Redis 故障时返回 None，由调用方回退数据库。"""
    client = get_redis_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 读取失败，降级直查数据库: %s", exc)
        return None


def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    """写入缓存；Redis 故障时静默忽略，不影响业务。"""
    client = get_redis_client()
    if client is None:
        return
    try:
        client.set(key, value, ex=ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 写入失败，忽略缓存: %s", exc)


def invalidate_monitor_cache(kind: str | None = None) -> None:
    """失效 mutation 影响的监控缓存；Redis 故障不得影响核心链路。"""
    client = get_redis_client()
    if client is None:
        return
    try:
        patterns = (
            (pattern for values in _MONITOR_CACHE_PATTERNS.values() for pattern in values)
            if kind is None
            else _MONITOR_CACHE_PATTERNS.get(kind, ())
        )
        keys = {
            key
            for pattern in patterns
            for key in client.scan_iter(match=pattern)
        }
        if keys:
            client.delete(*keys)
    except Exception as exc:  # noqa: BLE001 - cache-aside 失效失败时由短 TTL 兜底
        logger.warning("Redis 监控缓存失效失败，保留数据库写入结果: %s", exc)
