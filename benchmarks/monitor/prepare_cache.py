"""Reset only OMMS monitor cache keys and optionally prewarm the dashboard keys."""

from __future__ import annotations

import argparse
import json
import os
from urllib.request import Request, urlopen

import redis

from benchmarks.monitor.workload import (
    LOG_LIST_PATH,
    OS_SNAPSHOT_PATH,
    PROCESS_LIST_PATH,
    TOTAL_PATH,
    list_payload,
    log_payload,
    response_data,
    snapshot_payload,
)


CACHE_PATTERNS = ("omms:os:*", "omms:process:*", "omms:log_stats:*")


def request_json(base_url: str, method: str, path: str, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=60) as response:  # noqa: S310 - explicit benchmark target
        envelope = json.load(response)
    _, error = response_data(envelope)
    if error:
        raise RuntimeError(f"{path}: {error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("warm", "expiry"), required=True)
    parser.add_argument("--host", default="http://127.0.0.1:8004")
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0"))
    parser.add_argument("--date", default=os.getenv("OMMS_BENCH_DATE", ""))
    args = parser.parse_args()

    client = redis.Redis.from_url(args.redis_url, decode_responses=True)
    keys = {
        key
        for pattern in CACHE_PATTERNS
        for key in client.scan_iter(match=pattern)
    }
    if keys:
        client.delete(*keys)
    print(f"deleted_monitor_cache_keys={len(keys)}")

    if args.mode == "warm":
        request_json(args.host, "GET", TOTAL_PATH)
        request_json(args.host, "POST", OS_SNAPSHOT_PATH, snapshot_payload())
        request_json(args.host, "POST", PROCESS_LIST_PATH, list_payload())
        request_json(args.host, "POST", LOG_LIST_PATH, log_payload(date=args.date))
        print("warm_cache_preload=complete")


if __name__ == "__main__":
    main()
