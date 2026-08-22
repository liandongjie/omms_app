# -*- coding: utf-8 -*-
"""Redis 缓存层与 Service 缓存接入的单元测试。

测试环境（ENVIRONMENT=testing）下缓存自动禁用；本文件通过
monkeypatch 注入假 Redis 客户端 / 假 cache_get，验证缓存读写、
故障降级与缓存键口径。
"""
import asyncio
import json
from fnmatch import fnmatch

import app.services.ops_service as ops_service_module
import app.services.ws_manager as ws_manager_module
import app.utils.cache as cache_module
from app.schemas.ops_schema import OsStateItem, ProcessStateItem
from app.services.ops_service import OpsService
from tests.test_ops_service import FakeOpsService, cfg, fake_settings, state


class FakeRedisClient:
    """内存版 Redis 客户端桩，仅用于验证读写与异常路径。"""

    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value

    def scan_iter(self, match):
        return (key for key in list(self.store) if fnmatch(key, match))

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


class RaisingRedisClient:
    """get/set 都抛异常，模拟 Redis 故障。"""

    def get(self, key):
        raise RuntimeError("redis down")

    def set(self, key, value, ex=None):
        raise RuntimeError("redis down")

    def scan_iter(self, match):
        raise RuntimeError("redis down")

    def delete(self, *keys):
        raise RuntimeError("redis down")


def make_service():
    return FakeOpsService(
        cfgs=[cfg(machine_tag="m1", group_name="op")],
        states=[state(machine_tag="m1")],
    )


def test_redis_client_disabled_in_testing_environment():
    assert cache_module.get_redis_client() is None


def test_cache_get_set_round_trip(monkeypatch):
    client = FakeRedisClient()
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: client)
    cache_module.cache_set("k1", "v1", ttl_seconds=3)
    assert cache_module.cache_get("k1") == "v1"
    assert cache_module.cache_get("missing") is None


def test_cache_get_returns_none_on_redis_failure(monkeypatch):
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: RaisingRedisClient())
    assert cache_module.cache_get("k1") is None
    # 写入失败静默忽略，不影响调用方
    cache_module.cache_set("k1", "v1", ttl_seconds=3)


def test_state_mutation_invalidates_only_related_monitor_cache(monkeypatch):
    client = FakeRedisClient()
    client.store.update(
        {
            "omms:os:20260729:all:error=0": "old-os",
            "omms:process:20260729:all:error=0:state_only=1": "old-process",
            "omms:log_stats:20260729:all:error=0": "old-log",
        }
    )
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: client)

    cache_module.invalidate_monitor_cache("state")

    assert set(client.store) == {"omms:log_stats:20260729:all:error=0"}


def test_invalidation_makes_next_query_read_new_state(monkeypatch):
    client = FakeRedisClient()
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: client)
    service = FakeOpsService(
        cfgs=[cfg(machine_tag="m1", group_name="op")],
        states=[
            state(
                machine_tag="m1",
                dat='{"cpu": 0.1, "mem": 0.2, "disk": 0.3}',
            )
        ],
    )

    assert service.get_os_states(date="20260625")[0].cpu_usage == 0.1
    service.states[0].dat = '{"cpu": 0.9, "mem": 0.2, "disk": 0.3}'
    assert service.get_os_states(date="20260625")[0].cpu_usage == 0.1

    cache_module.invalidate_monitor_cache("state")

    assert service.get_os_states(date="20260625")[0].cpu_usage == 0.9


def test_invalidation_failure_is_safely_ignored(monkeypatch):
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: RaisingRedisClient())
    cache_module.invalidate_monitor_cache("state")


def test_api_falls_back_to_database_when_redis_is_unavailable(monkeypatch):
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: RaisingRedisClient())

    result = make_service().get_os_states(date="20260625")

    assert len(result) == 1
    assert result[0].machine_tag == "m1"


def test_ws_refresh_invalidates_cache_before_broadcast(monkeypatch):
    events = []
    monkeypatch.setattr(
        ws_manager_module,
        "invalidate_monitor_cache",
        lambda: events.append("invalidate"),
    )

    async def broadcast(message):
        events.append(message["event"])

    monkeypatch.setattr(ws_manager_module.manager, "broadcast", broadcast)

    asyncio.run(ws_manager_module.broadcast_refresh())

    assert events == ["invalidate", "refresh"]


def test_cache_key_normalizes_group_and_flags():
    service = make_service()
    assert service._cache_key("os", None, False, "20260729") == "omms:os:20260729:all:error=0"
    assert service._cache_key("os", "", False, "20260729") == "omms:os:20260729:all:error=0"
    assert service._cache_key("os", "all", True, "20260729") == "omms:os:20260729:all:error=1"
    assert service._cache_key("os", "op", False, "20260729") == "omms:os:20260729:op:error=0"
    process_key = service._cache_key(
        "process", None, False, "20260729", state_only=True
    )
    assert process_key.endswith("state_only=1")


def test_os_states_return_cached_items_without_db_access(monkeypatch):
    item = OsStateItem(
        machine_tag="cached-m1",
        group="op",
        cpu_usage=0.5,
        status="normal",
        message="ok",
    )
    payload = json.dumps([item.model_dump(mode="json")])
    hits = []
    monkeypatch.setattr(
        ops_service_module, "cache_get", lambda key: hits.append(key) or payload
    )
    service = FakeOpsService(cfgs=[], states=[])  # 缓存命中时不应访问 db 数据
    result = service.get_os_states(group=None, date="20260729")
    assert len(result) == 1
    assert result[0].machine_tag == "cached-m1"
    assert hits and hits[0] == "omms:os:20260729:all:error=0"


def test_os_states_fallback_to_db_when_cache_misses(monkeypatch):
    written = []
    monkeypatch.setattr(ops_service_module, "cache_get", lambda key: None)
    monkeypatch.setattr(
        ops_service_module, "cache_set", lambda key, value, ttl: written.append(key)
    )
    service = make_service()
    result = service.get_os_states(group=None, date="20260729")
    # 配置 + 状态都来自 Fake 数据，说明走的是计算路径
    assert len(result) == 1
    assert result[0].machine_tag == "m1"
    assert written and written[0].startswith("omms:os:20260729:all:")


def test_process_states_use_cache_and_state_only_key(monkeypatch):
    item = ProcessStateItem(
        machine_tag="cached-p1",
        group=None,
        process_name="proc",
        is_configured=False,
        status="normal",
        message="ok",
    )
    payload = json.dumps([item.model_dump(mode="json")])
    keys = []
    monkeypatch.setattr(
        ops_service_module, "cache_get", lambda key: keys.append(key) or payload
    )
    service = FakeOpsService(cfgs=[], states=[])
    result = service.get_process_states(
        group=None, date="20260729", include_state_only=True
    )
    assert result[0].machine_tag == "cached-p1"
    assert keys and keys[0].endswith("state_only=1")
