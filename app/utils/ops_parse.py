# -*- coding: utf-8 -*-
import ast
import json
from datetime import datetime, timedelta
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


def normalize_percent(value: Any) -> float | None:
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    # Historical ops_state data may store percent values as 0-1 ratios.
    if 0 <= number <= 1:
        return number * 100
    return number


def today_yyyymmdd(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d")
