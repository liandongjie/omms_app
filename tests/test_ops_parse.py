# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from app.utils.ops_parse import is_in_work_time, is_stale, parse_dat, parse_metric_value, parse_update_time


def test_parse_dat_supports_json_and_python_dict_string():
    assert parse_dat('{"cpu": 0.3, "mem": 0.61}') == {"cpu": 0.3, "mem": 0.61}
    assert parse_dat("{'pid': 100, 'pname': './bin/tlBinTradeLite'}") == {
        "pid": 100,
        "pname": "./bin/tlBinTradeLite",
    }


def test_parse_dat_failure_returns_empty_dict():
    assert parse_dat("{broken") == {}
    assert parse_dat(None) == {}


def test_parse_update_time_supports_known_formats():
    assert parse_update_time("20260625 22:56:57") == datetime(2026, 6, 25, 22, 56, 57)
    assert parse_update_time("2026-06-27 17:27:35") == datetime(2026, 6, 27, 17, 27, 35)
    assert parse_update_time("bad") is None


def test_is_stale_uses_three_minute_default():
    now = datetime(2026, 6, 25, 23, 0, 0)
    assert is_stale(now - timedelta(minutes=4), now=now)
    assert not is_stale(now - timedelta(minutes=2), now=now)
    assert is_stale(None, now=now)


def test_parse_metric_value_keeps_raw_metric_values():
    assert parse_metric_value(0.953) == 0.953
    assert parse_metric_value("0.37") == 0.37
    assert parse_metric_value(1) == 1.0
    assert parse_metric_value(90.8) == 90.8
    assert parse_metric_value("bad") is None

def test_is_in_work_time_supports_single_range():
    assert is_in_work_time("09:00:00-23:00:00", now=datetime(2026, 6, 25, 10, 0, 0))
    assert not is_in_work_time("09:00:00-23:00:00", now=datetime(2026, 6, 25, 8, 59, 59))


def test_is_in_work_time_supports_multiple_ranges():
    work_time = "09:00:00-15:00:00;21:00:00-23:00:00"

    assert is_in_work_time(work_time, now=datetime(2026, 6, 25, 10, 0, 0))
    assert not is_in_work_time(work_time, now=datetime(2026, 6, 25, 16, 0, 0))
    assert is_in_work_time(work_time, now=datetime(2026, 6, 25, 22, 0, 0))


def test_is_in_work_time_defaults_to_true_for_empty_or_bad_config():
    now = datetime(2026, 6, 25, 16, 0, 0)

    assert is_in_work_time(None, now=now)
    assert is_in_work_time("", now=now)
    assert is_in_work_time("   ", now=now)
    assert is_in_work_time("bad", now=now)
    assert is_in_work_time("09:00:00-bad", now=now)

