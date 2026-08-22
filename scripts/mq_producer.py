# -*- coding: utf-8 -*-
"""模拟上游生产者：把生成的 ops_state / ops_log 消息发布到 RabbitMQ。

用法（先 ``docker compose up -d`` 启动 RabbitMQ）：

  .\\.venv\\Scripts\\python.exe -m scripts.mq_producer --count 1000 --rate 20

- ``--kind state|log|both`` 控制消息类型（默认 both 按 OS/process/log 轮转）；
- ``--rate`` 每秒发布条数（0 表示不限速）；
- 消息格式与 ``scripts/mock_data.py`` 保持一致，且与消费端拓扑声明一致。
"""
import argparse
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timedelta

import pika

from app.services.mq_consumer import (
    EXCHANGE,
    ROUTING_LOG,
    ROUTING_STATE,
    declare_topology,
)
from scripts.mock_data import machine_tags, random_log_message, random_state_message

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv(
    "RABBITMQ_URL", "amqp://omms:omms_dev@127.0.0.1:5672/%2F"
)
MESSAGE_CYCLE = ("os", "process", "log")


def build_message(rng, machines, date, seed, kind, index):
    """确定性生成单条消息及 routing key，便于脱离 RabbitMQ 验证覆盖率。"""
    machine_tag, _ = machines[index % len(machines)]
    day_start = datetime.strptime(date + " 08:00:00", "%Y%m%d %H:%M:%S")
    update_time = (day_start + timedelta(seconds=(index * 7) % (14 * 3600))).strftime(
        "%Y%m%d %H:%M:%S"
    )

    if kind == "both":
        category = MESSAGE_CYCLE[index % len(MESSAGE_CYCLE)]
    elif kind == "state":
        category = MESSAGE_CYCLE[index % 2]
    else:
        category = "log"

    if category != "log":
        return (
            random_state_message(rng, date, machine_tag, category, update_time),
            ROUTING_STATE,
        )

    # 相同生成参数得到相同事件 ID；消息 redelivery 复用 payload，不会改变身份。
    event_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"omms-mq:{kind}:{seed}:{date}:{index}:{machine_tag}",
        )
    )
    return (
        random_log_message(rng, date, machine_tag, update_time, event_id),
        ROUTING_LOG,
    )


def build_properties(message):
    """日志的 AMQP message_id 与 payload event_id 使用同一业务身份。"""
    return pika.BasicProperties(
        delivery_mode=2,
        message_id=message.get("event_id"),
    )


def validate_generation(kind, count):
    if kind == "both" and count < len(MESSAGE_CYCLE):
        raise ValueError("--kind both 至少需要 --count 3 才能覆盖 OS/process/log")


def main():
    parser = argparse.ArgumentParser(description="模拟上游生产者")
    parser.add_argument("--count", type=int, default=1000, help="发布消息条数（默认 1000）")
    parser.add_argument("--rate", type=float, default=0, help="每秒发布条数，0 表示不限速（默认 0）")
    parser.add_argument("--kind", choices=["state", "log", "both"], default="both", help="消息类型（默认 both）")
    parser.add_argument("--machines", type=int, default=20, help="轮转机器台数（默认 20）")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="数据日期 YYYYMMDD（默认今天）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    args = parser.parse_args()
    try:
        validate_generation(args.kind, args.count)
    except ValueError as exc:
        parser.error(str(exc))

    rng = random.Random(args.seed)
    machines = machine_tags(args.machines, seed=args.seed)
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    # 与消费端保持一致的拓扑声明，保证生产者在消费端未启动时也能先就绪
    declare_topology(channel)

    started = time.perf_counter()
    published = 0
    for index in range(args.count):
        message, routing_key = build_message(
            rng, machines, args.date, args.seed, args.kind, index
        )

        channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=routing_key,
            body=json.dumps(message, ensure_ascii=False),
            properties=build_properties(message),
        )
        published += 1
        if args.rate > 0:
            time.sleep(1 / args.rate)

    elapsed = time.perf_counter() - started
    logger.info(
        "已发布 %d 条消息（kind=%s），耗时 %.1fs，均速 %.1f msg/s",
        published,
        args.kind,
        elapsed,
        published / elapsed if elapsed else 0,
    )
    connection.close()


if __name__ == "__main__":
    main()
