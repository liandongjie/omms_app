# -*- coding: utf-8 -*-
"""MQ 消费端单元测试。

用内存 SQLite 验证：ops_state 复合主键幂等 upsert、ops_log 事件去重、
级别归一化、ack/nack 语义。实际 RabbitMQ 连接行为依赖容器，不在单测范围。
"""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.ops_model import OpsLog, OpsState
from app.services.mq_consumer import _persist_message, handle_message
import app.services.mq_consumer as mq_consumer_module


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


class FakeChannel:
    def __init__(self):
        self.acked = []
        self.nacked = []

    def basic_ack(self, delivery_tag):
        self.acked.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue=False):
        self.nacked.append((delivery_tag, requeue))


def state_message(**overrides):
    message = {
        "kind": "state",
        "type": "os",
        "date": "20260729",
        "machine_tag": "op-service-01",
        "key": "os",
        "value": "os",
        "update_time": "20260729 09:40:28",
        "dat": '{"cpu": 0.02}',
    }
    message.update(overrides)
    return message


def log_message(**overrides):
    message = {
        "kind": "log",
        "date": "20260729",
        "machine_tag": "op-service-01",
        "log_name": "/var/log/omms/col_service_ops.log",
        "level": "ERROR",
        "log": "boom",
        "update_time": "20260729 09:40:28",
    }
    message.update(overrides)
    return message


def encode(message):
    return json.dumps(message).encode("utf-8")


def test_persist_state_message_is_idempotent(db_session):
    _persist_message(state_message(), db_session)
    db_session.commit()
    _persist_message(state_message(), db_session)
    db_session.commit()
    rows = db_session.query(OpsState).all()
    assert len(rows) == 1
    assert rows[0].machine_tag == "op-service-01"


def test_persist_state_updates_existing_row(db_session):
    _persist_message(state_message(dat='{"cpu": 0.1}'), db_session)
    db_session.commit()
    _persist_message(state_message(dat='{"cpu": 0.9}'), db_session)
    db_session.commit()
    rows = db_session.query(OpsState).all()
    assert len(rows) == 1
    assert rows[0].dat == '{"cpu": 0.9}'


def test_persist_log_message_appends_and_normalizes_level(db_session):
    # sqlite 不自动生成 BIGINT 主键，测试显式传入 log_id；MySQL 生产环境可缺省
    _persist_message(log_message(log_id=1, level="WARN"), db_session)
    _persist_message(log_message(log_id=2, level="error"), db_session)
    db_session.commit()
    rows = db_session.query(OpsLog).all()
    assert len(rows) == 2
    assert {row.level for row in rows} == {"warn", "error"}


def test_persist_same_log_event_only_once(db_session):
    _persist_message(log_message(log_id=10, event_id="event-10"), db_session)
    _persist_message(log_message(log_id=11, event_id="event-10"), db_session)
    db_session.commit()

    rows = db_session.query(OpsLog).all()
    assert len(rows) == 1
    assert rows[0].event_id == "event-10"


def test_persist_unsupported_kind_raises(db_session):
    with pytest.raises(ValueError):
        _persist_message({"kind": "unknown"}, db_session)


def test_handle_message_acks_on_success(db_session):
    channel = FakeChannel()
    handle_message(
        channel, SimpleNamespace(delivery_tag=1), None, encode(state_message()), db=db_session
    )
    assert channel.acked == [1]
    assert channel.nacked == []


def test_handle_message_is_idempotent_after_commit_redelivery(db_session):
    channel = FakeChannel()
    body = encode(log_message(log_id=20, event_id="redelivered-event"))

    handle_message(channel, SimpleNamespace(delivery_tag=6), None, body, db=db_session)
    handle_message(channel, SimpleNamespace(delivery_tag=7), None, body, db=db_session)

    assert db_session.query(OpsLog).count() == 1
    assert channel.acked == [6, 7]
    assert channel.nacked == []


def test_ack_failure_leaves_message_for_idempotent_redelivery(db_session):
    class FailedAckChannel(FakeChannel):
        def basic_ack(self, delivery_tag):
            raise RuntimeError("connection lost before ack")

    body = encode(log_message(log_id=21, event_id="ack-gap-event"))
    failed_channel = FailedAckChannel()
    with pytest.raises(RuntimeError, match="connection lost before ack"):
        handle_message(
            failed_channel, SimpleNamespace(delivery_tag=10), None, body, db=db_session
        )

    redelivery_channel = FakeChannel()
    handle_message(
        redelivery_channel, SimpleNamespace(delivery_tag=11), None, body, db=db_session
    )

    assert db_session.query(OpsLog).count() == 1
    assert failed_channel.nacked == []
    assert redelivery_channel.acked == [11]


def test_handle_message_uses_amqp_message_id_for_log_event(db_session):
    channel = FakeChannel()

    handle_message(
        channel,
        SimpleNamespace(delivery_tag=9),
        SimpleNamespace(message_id="amqp-event-9"),
        encode(log_message(log_id=30)),
        db=db_session,
    )

    assert db_session.query(OpsLog).one().event_id == "amqp-event-9"


def test_handle_message_commits_before_cache_invalidation_and_ack(db_session, monkeypatch):
    events = []
    original_commit = db_session.commit

    def commit():
        original_commit()
        events.append("commit")

    class OrderedChannel(FakeChannel):
        def basic_ack(self, delivery_tag):
            events.append("ack")
            super().basic_ack(delivery_tag)

    monkeypatch.setattr(db_session, "commit", commit)
    monkeypatch.setattr(
        mq_consumer_module,
        "invalidate_monitor_cache",
        lambda kind: events.append(f"invalidate:{kind}"),
    )

    channel = OrderedChannel()
    handle_message(
        channel, SimpleNamespace(delivery_tag=4), None, encode(state_message()), db=db_session
    )

    assert events == ["commit", "invalidate:state", "ack"]


def test_redis_failure_does_not_break_mutation(monkeypatch, db_session):
    class UnavailableRedis:
        def scan_iter(self, match):
            raise RuntimeError("redis down")

    monkeypatch.setattr("app.utils.cache.get_redis_client", lambda: UnavailableRedis())
    channel = FakeChannel()

    handle_message(
        channel, SimpleNamespace(delivery_tag=5), None, encode(state_message()), db=db_session
    )

    assert db_session.query(OpsState).count() == 1
    assert channel.acked == [5]
    assert channel.nacked == []


def test_cache_invalidation_exception_does_not_break_committed_mutation(
    monkeypatch, db_session
):
    monkeypatch.setattr(
        mq_consumer_module,
        "invalidate_monitor_cache",
        lambda kind: (_ for _ in ()).throw(RuntimeError("redis down")),
    )
    channel = FakeChannel()

    handle_message(
        channel, SimpleNamespace(delivery_tag=12), None, encode(state_message()), db=db_session
    )

    assert db_session.query(OpsState).count() == 1
    assert channel.acked == [12]
    assert channel.nacked == []


def test_db_failure_does_not_ack(monkeypatch, db_session):
    channel = FakeChannel()
    rolled_back = []

    monkeypatch.setattr(
        db_session,
        "commit",
        lambda: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    monkeypatch.setattr(db_session, "rollback", lambda: rolled_back.append(True))

    handle_message(
        channel, SimpleNamespace(delivery_tag=8), None, encode(state_message()), db=db_session
    )

    assert channel.acked == []
    assert channel.nacked == [(8, False)]
    assert rolled_back == [True]


def test_handle_message_nacks_on_invalid_json(db_session):
    channel = FakeChannel()
    handle_message(channel, SimpleNamespace(delivery_tag=2), None, b"{bad json", db=db_session)
    assert channel.nacked == [(2, False)]
    assert channel.acked == []


def test_handle_message_nacks_on_missing_fields(db_session):
    channel = FakeChannel()
    handle_message(
        channel,
        SimpleNamespace(delivery_tag=3),
        None,
        encode({"kind": "state"}),
        db=db_session,
    )
    assert channel.nacked == [(3, False)]
    assert channel.acked == []
