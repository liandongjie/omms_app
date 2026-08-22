"""Pure request definitions shared by Locust and benchmark smoke tests."""

from __future__ import annotations

import math
from typing import Any


TOTAL_PATH = "/api_omms/monitor/overview/total"
GROUP_PATH = "/api_omms/monitor/group/list"
OS_LIST_PATH = "/api_omms/monitor/overview/os/list"
PROCESS_LIST_PATH = "/api_omms/monitor/overview/process/list"
LOG_LIST_PATH = "/api_omms/monitor/overview/log/list"

REQUIRED_CASES = {
    "total": ("GET", TOTAL_PATH),
    "os_list": ("POST", OS_LIST_PATH),
    "process_list": ("POST", PROCESS_LIST_PATH),
    "log_list": ("POST", LOG_LIST_PATH),
    "log_level": ("POST", LOG_LIST_PATH),
    "log_only_error": ("POST", LOG_LIST_PATH),
    "log_machine": ("POST", LOG_LIST_PATH),
}


def list_payload(*, page_no: int = 1, page_size: int = 100, group: str = "") -> dict[str, Any]:
    """Match the frontend OS/process list request shape."""
    return {
        "group": group,
        "page_no": page_no,
        "page_size": page_size,
        "sort_by": "",
        "sort_order": "",
    }


def log_payload(
    *,
    page_no: int = 1,
    page_size: int = 20,
    group: str = "",
    machine_tag: str | None = None,
    only_error: int = 0,
    level: str = "",
    date: str = "",
) -> dict[str, Any]:
    """Match ``buildLogListParams`` and its supported backend filters."""
    payload = {
        "group": group,
        "only_error": only_error,
        "level": level,
        "date": date,
        "page_no": page_no,
        "page_size": page_size,
        "sort_by": "",
        "sort_order": "",
    }
    if machine_tag:
        payload["machine_tag"] = machine_tag
    return payload


def response_data(payload: Any) -> tuple[Any | None, str | None]:
    """Validate the application envelope so HTTP 200 business errors fail in Locust."""
    if not isinstance(payload, dict):
        return None, "response is not a JSON object"
    if payload.get("code") != 200:
        return None, f"application code is {payload.get('code')!r}"
    if "data" not in payload:
        return None, "response has no data field"
    return payload["data"], None


def os_page_count(data: Any, requested_page_size: int = 100) -> int:
    """Return the number of pages the frontend would fetch for the OS table."""
    if not isinstance(data, dict):
        return 1
    details = data.get("details")
    fallback_total = len(details) if isinstance(details, list) else 0
    total = max(0, int(data.get("total", fallback_total)))
    page_size = max(1, int(data.get("page_size", requested_page_size)))
    return max(1, math.ceil(total / page_size))
