# -*- coding: utf-8 -*-
import ast
import json
from datetime import datetime, time, timedelta
from typing import Any


def parse_dat(dat: str | None) -> dict:
    """把上报的 dat 文本解析为字典。

    Args:
        dat: JSON 或 Python 字面量形式的原始文本。

    Returns:
        解析成功且结果为字典时返回该字典，否则返回空字典。
    """
    if not dat:
        return {}

    # 上报数据优先按标准 JSON 解析，同时兼容 Python 字面量格式。
    try:
        parsed = json.loads(dat)
    except (TypeError, ValueError):
        try:
            parsed = ast.literal_eval(dat)
        except (SyntaxError, ValueError, TypeError):
            return {}

    return parsed if isinstance(parsed, dict) else {}


def parse_update_time(value: str | None) -> datetime | None:
    """解析支持的上报时间格式。

    Args:
        value: 紧凑日期或带连字符日期形式的时间文本。

    Returns:
        解析后的 datetime；输入缺失或格式不受支持时返回 None。
    """
    if not value:
        return None

    # 同时接受紧凑日期和带连字符日期，其余格式统一视为无有效时间。
    text = value.strip()
    for fmt in ("%Y%m%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def is_stale(update_time: str | datetime | None, minutes: int = 3, now: datetime | None = None) -> bool:
    """判断上报时间是否超过允许的更新时间窗口。

    Args:
        update_time: 时间文本、datetime 或空值。
        minutes: 允许的数据时效分钟数。
        now: 用于比较的当前时间；缺失时读取本地当前时间。

    Returns:
        时间缺失、无法解析或早于时效窗口时返回 True。
    """
    if isinstance(update_time, str):
        parsed_time = parse_update_time(update_time)
    else:
        parsed_time = update_time

    # 缺失或无法解析的时间无法证明数据仍新鲜，因此按过期处理。
    if parsed_time is None:
        return True

    current_time = now or datetime.now()
    return current_time - parsed_time > timedelta(minutes=minutes)


def _parse_work_clock(value: str) -> time | None:
    """解析工作时间配置中的单个时钟值。

    Args:
        value: ``HH:MM:SS`` 格式的文本。

    Returns:
        解析后的 time；格式无效时返回 None。
    """
    try:
        return datetime.strptime(value.strip(), "%H:%M:%S").time()
    except ValueError:
        return None


def is_in_work_time(work_time: str | None, now: datetime | None = None) -> bool:
    """判断当前本地时间是否落在配置的任一工作时间段内。

    支持单个时间段、分号分隔的多个时间段，以及起始时间晚于结束时间的跨午夜区间。
    配置缺失或格式错误时返回 True，使调用方继续执行工作时间内的离线判断。

    Args:
        work_time: 工作时间配置，例如 ``09:00:00-15:00:00;21:00:00-23:00:00``。
        now: 用于判断的当前时间；缺失时读取本地当前时间。

    Returns:
        当前时间位于任一有效区间，或配置缺失/无效时返回 True；否则返回 False。
    """
    # 配置缺失或格式错误时按“在工作时间”处理，避免错误配置跳过离线判断。
    if not work_time or not work_time.strip():
        return True

    current_time = (now or datetime.now()).time()
    ranges = [part.strip() for part in work_time.split(";") if part.strip()]
    if not ranges:
        return True

    for item in ranges:
        pieces = item.split("-", 1)
        if len(pieces) != 2:
            return True

        start = _parse_work_clock(pieces[0])
        end = _parse_work_clock(pieces[1])
        if start is None or end is None:
            return True

        if start <= end:
            if start <= current_time <= end:
                return True
        else:
            # Overnight range, for example 21:00:00-02:00:00.
            if current_time >= start or current_time <= end:
                return True

    return False


def parse_metric_value(value: Any) -> float | None:
    """把监控指标转换为浮点数。

    Args:
        value: 原始指标值。

    Returns:
        可转换时返回浮点数，空值或非法数值返回 None。
    """
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def today_yyyymmdd(now: datetime | None = None) -> str:
    """生成 YYYYMMDD 格式的日期字符串。

    Args:
        now: 指定日期时间；缺失时读取本地当前时间。

    Returns:
        八位日期字符串。
    """
    return (now or datetime.now()).strftime("%Y%m%d")
