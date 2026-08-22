# -*- coding: utf-8 -*-
"""生成压测/演示用基准数据，直接写入 MySQL。

用法（配合 docker compose 启动的 MySQL，默认 127.0.0.1:3307）：

  .\\.venv\\Scripts\\python.exe -m scripts.generate_data --states 50000 --logs 50000 --machines 50 --truncate

- ``--truncate`` 会清空三张表并重建配置与数据，适合做可重复的压测基线；
- 不带 ``--truncate`` 时补齐配置、幂等更新状态并追加日志；已有配置不会重复插入。
- 连接参数可用环境变量 DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD 覆盖。
"""
import argparse
import logging
import os
import random
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.models.ops_model import OpsCfg, OpsLog, OpsState
from scripts.mock_data import machine_tags, random_log_message, random_state_message

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 2000

DEFAULT_DB = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3307")),
    "name": os.getenv("DB_NAME", "omms_app"),
    "user": os.getenv("DB_USER", "omms"),
    "password": os.getenv("DB_PASSWORD", "omms_dev"),
}


def build_engine():
    url = (
        f"mysql+pymysql://{DEFAULT_DB['user']}:{DEFAULT_DB['password']}"
        f"@{DEFAULT_DB['host']}:{DEFAULT_DB['port']}/{DEFAULT_DB['name']}?charset=utf8mb4"
    )
    return create_engine(url, pool_pre_ping=True)


def generate_configs(db, machines):
    """按现有逻辑复合键补齐 ops_cfg，重复运行不插入已有配置。

    调用方需处于事务中（engine.begin()），本函数不负责 commit。
    """
    rows = []
    for machine_tag, group in machines:
        rows.append(
            {
                "type": "os",
                "machine_tag": machine_tag,
                "group": group,
                "key": "os",
                "value": "os",
                "work_time": "09:00:00-23:00:00",
                "status": 1,
            }
        )
        for binary, cfg_value in [
            ("./bin/tlBinTradeLite", "sys"),
            ("./bin/tlBinFutLite", "sys"),
            ("/opt/anaconda3/bin/python", "col_service_ops"),
        ]:
            rows.append(
                {
                    "type": "process",
                    "machine_tag": machine_tag,
                    "group": group,
                    "key": binary,
                    "value": cfg_value,
                    "work_time": "08:50:00-15:30:00;20:50:00-23:55:00",
                    "status": 1,
                }
            )
    existing = {
        tuple(row)
        for row in db.execute(
            select(
                OpsCfg.type,
                OpsCfg.machine_tag,
                OpsCfg.group_name,
                OpsCfg.cfg_key,
                OpsCfg.value,
            ).where(OpsCfg.machine_tag.in_([machine[0] for machine in machines]))
        ).all()
    }
    missing = [
        row
        for row in rows
        if (row["type"], row["machine_tag"], row["group"], row["key"], row["value"])
        not in existing
    ]
    for start in range(0, len(missing), BATCH_SIZE):
        db.execute(OpsCfg.__table__.insert(), missing[start : start + BATCH_SIZE])
    logger.info("已写入 ops_cfg %d 条", len(missing))


def insert_state_messages(db, messages):
    """按复合主键幂等 upsert，重复执行不会产生重复状态。调用方管理事务。"""
    for start in range(0, len(messages), BATCH_SIZE):
        batch = messages[start : start + BATCH_SIZE]
        stmt = mysql_insert(OpsState).values(
            [
                {
                    "date": m["date"],
                    "type": m["type"],
                    "machine_tag": m["machine_tag"],
                    "key": m["key"],
                    "value": m["value"],
                    "update_time": m["update_time"],
                    "dat": m["dat"],
                }
                for m in batch
            ]
        )
        stmt = stmt.on_duplicate_key_update(
            update_time=stmt.inserted.update_time, dat=stmt.inserted.dat
        )
        db.execute(stmt)
    logger.info("已写入 ops_state %d 条", len(messages))


def insert_log_messages(db, messages):
    """日志为追加式写入；调用方管理事务。"""
    for start in range(0, len(messages), BATCH_SIZE):
        batch = messages[start : start + BATCH_SIZE]
        db.execute(
            OpsLog.__table__.insert(),
            [
                {
                    "event_id": m["event_id"],
                    "date": m["date"],
                    "machine_tag": m["machine_tag"],
                    "log_name": m["log_name"],
                    "level": m["level"],
                    "log": m["log"],
                    "update_time": m["update_time"],
                }
                for m in batch
            ],
        )
    logger.info("已写入 ops_log %d 条", len(messages))


def build_states(rng, machines, count, date):
    """按机器轮转生成指定数量的状态消息，时间在 08:00-22:00 内错开。"""
    messages = []
    day_start = datetime.strptime(date + " 08:00:00", "%Y%m%d %H:%M:%S")
    for index in range(count):
        machine_tag, _ = machines[index % len(machines)]
        state_type = "os" if index % 2 == 0 else "process"
        seconds = (index * 7) % (14 * 3600)
        update_time = (day_start + timedelta(seconds=seconds)).strftime("%Y%m%d %H:%M:%S")
        messages.append(
            random_state_message(rng, date, machine_tag, state_type, update_time)
        )
    return messages


def build_logs(rng, machines, count, date, event_namespace=None):
    """按机器轮转生成指定数量的日志消息，时间在当天内错开。"""
    messages = []
    # 同一次生成内按 namespace 确定性派生；非 truncate 的下一次运行使用新 namespace。
    event_namespace = event_namespace or uuid.uuid4()
    day_start = datetime.strptime(date + " 08:00:00", "%Y%m%d %H:%M:%S")
    for index in range(count):
        machine_tag, _ = machines[index % len(machines)]
        seconds = (index * 11) % (14 * 3600)
        update_time = (day_start + timedelta(seconds=seconds)).strftime("%Y%m%d %H:%M:%S")
        event_id = str(
            uuid.uuid5(
                event_namespace,
                f"{date}:{index}:{machine_tag}",
            )
        )
        messages.append(
            random_log_message(rng, date, machine_tag, update_time, event_id)
        )
    return messages


def main():
    parser = argparse.ArgumentParser(description="生成 OMMS 压测/演示基准数据")
    parser.add_argument("--states", type=int, default=50000, help="ops_state 条数（默认 50000）")
    parser.add_argument("--logs", type=int, default=50000, help="ops_log 条数（默认 50000）")
    parser.add_argument("--machines", type=int, default=50, help="生成机器台数（默认 50）")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="数据日期 YYYYMMDD（默认今天）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，保证可重复（默认 42）")
    parser.add_argument("--truncate", action="store_true", help="清空三张表后重建（可重复压测基线）")
    args = parser.parse_args()

    started = time.perf_counter()
    rng = random.Random(args.seed)
    machines = machine_tags(args.machines, seed=args.seed)
    logger.info("生成 %d 台机器: %s ...", len(machines), machines[0][0])

    engine = build_engine()
    with engine.begin() as connection:
        if args.truncate:
            connection.execute(text("TRUNCATE TABLE ops_cfg"))
            connection.execute(text("TRUNCATE TABLE ops_state"))
            connection.execute(text("TRUNCATE TABLE ops_log"))
            logger.info("已清空 ops_cfg / ops_state / ops_log")
        generate_configs(connection, machines)
        insert_state_messages(connection, build_states(rng, machines, args.states, args.date))
        insert_log_messages(connection, build_logs(rng, machines, args.logs, args.date))

    elapsed = time.perf_counter() - started
    logger.info(
        "完成：ops_cfg=%d, ops_state=%d, ops_log=%d，耗时 %.1fs",
        len(machines) * 4,
        args.states,
        args.logs,
        elapsed,
    )


if __name__ == "__main__":
    main()
