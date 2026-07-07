# -*- coding: utf-8 -*-
import ast
import json
from datetime import datetime, time, timedelta
from typing import Any


def parse_dat(dat: str | None) -> dict:
    if not dat:
        return {}

    try:
        parsed = json.loads(dat)
    except (TypeError, ValueError):
        try:
            parsed = ast.literal_eval(dat)
        except (SyntaxError, ValueError, TypeError):
            return {}

    return parsed if isinstance(parsed, dict) else {}


def parse_update_time(value: str | None) -> datetime | None:
    if not value:
        return None

    text = value.strip()
    for fmt in ("%Y%m%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def is_stale(update_time: str | datetime | None, minutes: int = 3, now: datetime | None = None) -> bool:
    if isinstance(update_time, str):
        parsed_time = parse_update_time(update_time)
    else:
        parsed_time = update_time

    if parsed_time is None:
        return True

    current_time = now or datetime.now()
    return current_time - parsed_time > timedelta(minutes=minutes)


def _parse_work_clock(value: str) -> time | None:
    try:
        return datetime.strptime(value.strip(), "%H:%M:%S").time()
    except ValueError:
        return None


def is_in_work_time(work_time: str | None, now: datetime | None = None) -> bool:
    """Return whether local time falls in the configured work_time ranges.

    Supported formats:
    - 09:00:00-23:00:00
    - 09:00:00-15:00:00;21:00:00-23:00:00

    Empty or malformed values default to True so a bad config does not hide
    offline alarms entirely.
    """
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
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def today_yyyymmdd(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d")
