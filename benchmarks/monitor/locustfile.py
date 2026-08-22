"""Locust workload matching the OMMS dashboard refresh and log filter actions."""

from __future__ import annotations

import os

import gevent
from locust import HttpUser, between, task

from benchmarks.monitor.workload import (
    GROUP_PATH,
    LOG_LIST_PATH,
    OS_SNAPSHOT_PATH,
    PROCESS_LIST_PATH,
    TOTAL_PATH,
    list_payload,
    log_payload,
    response_data,
    snapshot_payload,
)


CACHE_SCENARIO = os.getenv("OMMS_CACHE_SCENARIO", "expiry").strip().lower()
if CACHE_SCENARIO not in {"warm", "expiry"}:
    raise ValueError("OMMS_CACHE_SCENARIO must be warm or expiry")

BENCHMARK_DATE = os.getenv("OMMS_BENCH_DATE", "").strip()
BENCHMARK_LEVEL = os.getenv("OMMS_BENCH_LEVEL", "error").strip().lower()
BENCHMARK_MACHINE = os.getenv("OMMS_BENCH_MACHINE_TAG", "fut-col-002").strip()
WAIT_MIN = float(os.getenv("OMMS_WAIT_MIN_SECONDS", "4.5"))
WAIT_MAX = float(os.getenv("OMMS_WAIT_MAX_SECONDS", "5.5"))


class MonitorDashboardUser(HttpUser):
    """A visible dashboard plus occasional real log-filter interactions."""

    wait_time = between(WAIT_MIN, WAIT_MAX)

    def _name(self, operation: str) -> str:
        return f"{CACHE_SCENARIO}:{operation}"

    def _request(self, method: str, path: str, *, name: str, json=None):
        with self.client.request(
            method,
            path,
            json=json,
            name=self._name(name),
            catch_response=True,
        ) as response:
            if response.status_code >= 400:
                response.failure(f"HTTP {response.status_code}")
                return None
            try:
                payload = response.json()
            except ValueError:
                response.failure("response is not JSON")
                return None
            data, error = response_data(payload)
            if error:
                response.failure(error)
                return None
            return data

    def on_start(self):
        # 页面挂载时仅加载一次分组列表。
        self._request("GET", GROUP_PATH, name="GET group list")

    def _total(self):
        self._request("GET", TOTAL_PATH, name="GET total")

    def _os_snapshot(self):
        self._request(
            "POST",
            OS_SNAPSHOT_PATH,
            name="POST os snapshot",
            json=snapshot_payload(),
        )

    def _process_list(self):
        self._request(
            "POST",
            PROCESS_LIST_PATH,
            name="POST process list",
            json=list_payload(),
        )

    def _log_list(self):
        self._request(
            "POST",
            LOG_LIST_PATH,
            name="POST log list",
            json=log_payload(date=BENCHMARK_DATE),
        )

    @task(12)
    def refresh_dashboard(self):
        # Vue 使用 Promise.all 并发刷新四个区块；OS 后续页在首响应后并发补齐。
        gevent.joinall(
            [
                gevent.spawn(self._total),
                gevent.spawn(self._os_snapshot),
                gevent.spawn(self._process_list),
                gevent.spawn(self._log_list),
            ]
        )

    @task(1)
    def filter_log_level(self):
        self._request(
            "POST",
            LOG_LIST_PATH,
            name="POST log level filter",
            json=log_payload(level=BENCHMARK_LEVEL, date=BENCHMARK_DATE),
        )

    @task(1)
    def filter_log_only_error(self):
        self._request(
            "POST",
            LOG_LIST_PATH,
            name="POST log only_error",
            json=log_payload(only_error=1, date=BENCHMARK_DATE),
        )

    @task(1)
    def filter_log_machine(self):
        self._request(
            "POST",
            LOG_LIST_PATH,
            name="POST log machine filter",
            json=log_payload(machine_tag=BENCHMARK_MACHINE, date=BENCHMARK_DATE),
        )
