# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from app.utils.ops_parse import is_stale, normalize_percent, parse_dat, parse_update_time


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


def test_normalize_percent_supports_ratio_and_percent_values():
    assert normalize_percent(0.953) == 95.3
    assert normalize_percent(95.3) == 95.3
    assert normalize_percent("0.37") == 37
    assert normalize_percent("bad") is None
