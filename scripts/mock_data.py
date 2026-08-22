# -*- coding: utf-8 -*-
"""模拟上游数据生成器（供 generate_data / mq_producer 复用）。

生成的消息格式与 docker/mysql/init 中的脱敏样例保持一致：
- ops_state：``dat`` 为 JSON 字符串，进程的 ``value`` 为 JSON 数组字符串（含盘次 yaml）；
- ops_log：日志文本带 ``[level]`` 标记，``level`` 归一小写。
"""
import json
import random

# 进程二进制与配置模板（与初始化样例对齐，_am/_pm 后缀供盘次识别）
PROCESS_BINARIES = [
    "./bin/tlBinTradeLite",
    "./bin/tlBinFutLite",
    "/opt/anaconda3/bin/python",
]
PROCESS_CONFIG_TEMPLATES = {
    "./bin/tlBinTradeLite": ["sys_simnow.yaml", "user_simnow_{date}_{session}.yaml"],
    "./bin/tlBinFutLite": ["sys_demo.yaml", "user_demo_{date}_{session}.yaml"],
    "/opt/anaconda3/bin/python": ["lk_strategy_fw.py", "task_col_service_ops.yaml"],
}
LOG_NAME_TEMPLATES = [
    "/var/log/omms/col_service_ops.log",
    "/var/log/omms/trade_{date}_{session}.log",
]
LOG_TEMPLATES = {
    "info": "[{ts}][info] [{name}] START, version=v2601.0.1, args=task.yaml/null, freq=2000",
    "warn": "[{ts}][warn] [{name}] retry=2, timeout after 5000ms",
    "error": "[{ts}][error] [{name}] connection timeout, retry=3",
}
# 生成机器时按此模板循环分配分组，保证各分组都有机器
MACHINE_PREFIX_GROUPS = [
    ("op-service-", "op"),
    ("fut-col-", "op"),
    ("algo-cta-", "algo00x"),
    ("algo-fut-", "algo00x"),
    ("etf-build-", "etf"),
]


def machine_tags(count: int, seed: int | None = None) -> list[tuple[str, str]]:
    """生成 count 台机器的 ``(machine_tag, group)`` 列表，分组分布与样例一致。"""
    rng = random.Random(seed)
    result = []
    index = 0
    while len(result) < count:
        prefix, group = MACHINE_PREFIX_GROUPS[index % len(MACHINE_PREFIX_GROUPS)]
        result.append((f"{prefix}{index + 1:03d}", group))
        index += 1
    return result


def random_state_message(rng, date: str, machine_tag: str, state_type: str, update_time: str) -> dict:
    """生成一条 ops_state 消息（dict，可直接 JSON 序列化）。"""
    if state_type == "os":
        return {
            "kind": "state",
            "type": "os",
            "date": date,
            "machine_tag": machine_tag,
            "key": "os",
            "value": "os",
            "update_time": update_time,
            "dat": json.dumps(
                {
                    "cpu": round(rng.uniform(0, 1), 4),
                    "mem": round(rng.uniform(0, 1), 4),
                    "disk": round(rng.uniform(0, 1), 4),
                    "disk_home": round(rng.uniform(-1, 1), 4),
                }
            ),
        }

    binary = rng.choice(PROCESS_BINARIES)
    session = rng.choice(["am", "pm"])
    configs = [
        item.format(date=date, session=session) if "{" in item else item
        for item in PROCESS_CONFIG_TEMPLATES[binary]
    ]
    dat = {
        "pid": rng.randint(10000, 999999),
        "pname": binary,
        "cpu": round(rng.uniform(0, 1), 3),
        "mem": round(rng.uniform(50, 8000), 3),
    }
    if machine_tag.startswith("algo"):
        dat["algo00x_cfg"] = f"{rng.randint(0, 99)}/{rng.randint(0, 99)}"
    return {
        "kind": "state",
        "type": "process",
        "date": date,
        "machine_tag": machine_tag,
        "key": binary,
        "value": json.dumps(configs),
        "update_time": update_time,
        "dat": json.dumps(dat),
    }


def random_log_message(
    rng, date: str, machine_tag: str, update_time: str, event_id: str
) -> dict:
    """生成一条 ops_log 消息（dict）。"""
    level = rng.choices(["info", "warn", "error"], weights=[80, 15, 5])[0]
    name = rng.choice(LOG_NAME_TEMPLATES).format(date=date, session=rng.choice(["am", "pm"]))
    ts = f"{update_time}.000000"
    return {
        "kind": "log",
        "event_id": event_id,
        "date": date,
        "machine_tag": machine_tag,
        "log_name": name,
        "level": level,
        "log": LOG_TEMPLATES[level].format(ts=ts, name=name),
        "update_time": update_time,
    }
