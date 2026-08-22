import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.monitor.capture_environment import sanitized_url
from benchmarks.monitor.summarize import build_summary
from benchmarks.monitor.workload import (
    REQUIRED_CASES,
    list_payload,
    log_payload,
    os_page_count,
    response_data,
)


ROOT = Path(__file__).resolve().parents[1]
LOCUSTFILE = ROOT / "benchmarks" / "monitor" / "locustfile.py"


def test_monitor_workload_covers_required_endpoints_and_filters():
    assert set(REQUIRED_CASES) == {
        "total",
        "os_list",
        "process_list",
        "log_list",
        "log_level",
        "log_only_error",
        "log_machine",
    }
    assert list_payload() == {
        "group": "",
        "page_no": 1,
        "page_size": 100,
        "sort_by": "",
        "sort_order": "",
    }
    assert log_payload(level="ERROR")["level"] == "ERROR"
    assert log_payload(only_error=1)["only_error"] == 1
    assert log_payload(machine_tag="m1")["machine_tag"] == "m1"


def test_monitor_workload_validates_envelope_and_os_pagination():
    data, error = response_data({"code": 200, "data": {"total": 201, "page_size": 100}})
    assert error is None
    assert os_page_count(data) == 3
    assert response_data({"code": 500, "data": None})[1]


def test_environment_snapshot_redacts_redis_credentials():
    assert sanitized_url("redis://user:secret@127.0.0.1:6380/2") == "redis://127.0.0.1:6380/2"


def test_locust_summary_records_rps_percentiles_and_failure_rate(tmp_path):
    stats = tmp_path / "stats.csv"
    stats.write_text(
        "Name,Request Count,Failure Count,Requests/s,50%,95%,99%\n"
        "Aggregated,100,2,12.5,10,40,80\n",
        encoding="utf-8",
    )

    summary = build_summary(stats, scenario="warm", users=10)

    assert summary == {
        "cache_scenario": "warm",
        "users": 10,
        "request_count": 100,
        "failure_count": 2,
        "failure_rate_percent": 2.0,
        "rps": 12.5,
        "p50_ms": 10.0,
        "p95_ms": 40.0,
        "p99_ms": 80.0,
    }


def test_locustfile_compiles_and_starts_when_benchmark_dependency_is_installed():
    source = LOCUSTFILE.read_text(encoding="utf-8")
    compile(source, str(LOCUSTFILE), "exec")
    if importlib.util.find_spec("locust") is None:
        pytest.skip("benchmark-only Locust dependency is not installed")

    result = subprocess.run(
        [sys.executable, "-m", "locust", "-f", str(LOCUSTFILE), "--list"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "MonitorDashboardUser" in result.stdout
