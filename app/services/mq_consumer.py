# -*- coding: utf-8 -*-
"""RabbitMQ 消费端：把上游数据消息写入 MySQL。

链路：生产者 → RabbitMQ → 本消费端 → MySQL → API → 前端。

可靠性设计（也是面试可讲的决策点）：
- 手动 ack：消息落库成功后才确认；进程崩溃时未确认消息由 RabbitMQ 重新投递，避免丢消息；
- 幂等写入：ops_state 使用数据库原子 upsert；ops_log 使用稳定事件 ID 去重；
- 死信队列：处理失败的消息 nack 且不重回队列，转入死信队列便于排查；
- 断线重连：后台线程循环重试，RabbitMQ 不可用不影响监控 API 本身。
"""
import hashlib
import json
import logging
import threading

import pika
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import get_settings
from app.models.ops_model import OpsLog, OpsState
from app.utils.cache import invalidate_monitor_cache
from app.utils.db import SessionLocal

logger = logging.getLogger(__name__)

EXCHANGE = "omms.ops"
EXCHANGE_TYPE = "topic"
QUEUE = "omms.ops.data"
DEAD_LETTER_EXCHANGE = "omms.ops.dlx"
DEAD_LETTER_QUEUE = "omms.ops.data.dlq"
ROUTING_STATE = "ops.state"
ROUTING_LOG = "ops.log"
RECONNECT_INTERVAL_SECONDS = 5


def declare_topology(channel):
    """声明交换机、主队列、死信队列及绑定。

    主队列绑定死信交换机：nack(requeue=False) 的消息自动转入死信队列。
    """
    channel.exchange_declare(exchange=EXCHANGE, exchange_type=EXCHANGE_TYPE, durable=True)
    channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(
        queue=QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": "dead",
        },
    )
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(exchange=DEAD_LETTER_EXCHANGE, queue=DEAD_LETTER_QUEUE, routing_key="dead")
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=ROUTING_STATE)
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=ROUTING_LOG)


def _connect(settings):
    """建立连接并完成拓扑声明。"""
    parameters = pika.URLParameters(settings.RABBITMQ_URL)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    declare_topology(channel)
    channel.basic_qos(prefetch_count=10)
    return connection, channel


def _persist_message(message: dict, db) -> None:
    """按消息类型写入数据库；失败抛异常，由调用方决定 ack/nack。"""
    kind = message.get("kind")
    if kind == "state":
        values = {
            "date": str(message["date"]),
            "type": message["type"],
            "machine_tag": message["machine_tag"],
            "state_key": message["key"],
            "value": str(message["value"]),
            "update_time": message.get("update_time"),
            "dat": message.get("dat"),
        }
        if db.get_bind().dialect.name == "mysql":
            statement = mysql_insert(OpsState).values(**values)
            statement = statement.on_duplicate_key_update(
                update_time=statement.inserted.update_time,
                dat=statement.inserted.dat,
            )
        else:
            # 测试使用 SQLite；生产链路只走上面的 MySQL 原子 upsert。
            statement = sqlite_insert(OpsState).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=["date", "type", "machine_tag", "key", "value"],
                set_={
                    "update_time": statement.excluded.update_time,
                    "dat": statement.excluded.dat,
                },
            )
        db.execute(statement)
    elif kind == "log":
        event_id = message.get("event_id")
        if not event_id:
            # 兼容旧生产者：同一消息 redelivery 的规范化 payload 哈希保持稳定。
            payload = json.dumps(
                message, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            event_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        values = {
            "event_id": str(event_id),
            "date": message.get("date"),
            "machine_tag": message.get("machine_tag"),
            "log_name": message.get("log_name"),
            "level": (message.get("level") or "").lower(),
            "log": message.get("log"),
            "update_time": message.get("update_time"),
        }
        if db.get_bind().dialect.name == "mysql":
            statement = mysql_insert(OpsLog).values(**values)
            statement = statement.on_duplicate_key_update(event_id=statement.inserted.event_id)
        else:
            # SQLite 的 BIGINT 主键不自增，单测显式提供 log_id；MySQL 始终由数据库生成。
            values["log_id"] = message.get("log_id")
            statement = sqlite_insert(OpsLog).values(**values).on_conflict_do_nothing()
        db.execute(statement)
    else:
        raise ValueError(f"unsupported message kind: {kind!r}")


def handle_message(channel, method, properties, body, db=None):
    """处理单条消息：落库成功后 ack；解析/落库失败 nack 进死信队列。"""
    try:
        message = json.loads(body.decode("utf-8"))
        if message.get("kind") == "log" and not message.get("event_id"):
            message_id = getattr(properties, "message_id", None)
            if message_id:
                message["event_id"] = message_id
        own_session = db is None
        session = db or SessionLocal()
        try:
            _persist_message(message, session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if own_session:
                session.close()
    except Exception as exc:  # noqa: BLE001 - 失败必须进死信，不允许阻塞消费
        logger.warning("消息处理失败，转入死信队列: %s", exc)
        try:
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception:
            pass
        return

    # 先提交数据库，再失效旁路缓存，最后 ack；ack 失败时让连接层触发 redelivery。
    try:
        invalidate_monitor_cache(message["kind"])
    except Exception as exc:  # noqa: BLE001 - Redis 故障不能破坏已提交写入
        logger.warning("Redis 缓存失效失败，保留数据库写入结果: %s", exc)
    channel.basic_ack(delivery_tag=method.delivery_tag)


class MQConsumer:
    """后台线程消费 RabbitMQ 消息并写入 MySQL。"""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._stop_event = threading.Event()
        self._thread = None
        self._connection = None
        self._channel = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="omms-mq-consumer", daemon=True
        )
        self._thread.start()
        logger.info("MQ 消费端线程已启动")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def shutdown(self) -> None:
        self._stop_event.set()
        connection = self._connection
        channel = self._channel
        if (
            connection is not None
            and connection.is_open
            and channel is not None
            and channel.is_open
        ):
            try:
                connection.add_callback_threadsafe(channel.stop_consuming)
            except Exception:
                pass

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._consume_once()
            except Exception as exc:  # noqa: BLE001 - 连接失败需循环重试
                logger.warning(
                    "MQ 消费异常，%d 秒后重连: %s", RECONNECT_INTERVAL_SECONDS, exc
                )
                self._stop_event.wait(RECONNECT_INTERVAL_SECONDS)

    def _consume_once(self) -> None:
        connection, channel = _connect(self.settings)
        self._connection = connection
        self._channel = channel
        channel.basic_consume(queue=QUEUE, on_message_callback=self._on_message)
        try:
            channel.start_consuming()
        finally:
            self._connection = None
            self._channel = None
            try:
                connection.close()
            except Exception:
                pass

    def _on_message(self, channel, method, properties, body):
        handle_message(channel, method, properties, body)
