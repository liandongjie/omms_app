"""Capture a credential-free benchmark environment and data snapshot as JSON."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pymysql
import redis


TABLES = ("ops_cfg", "ops_state", "ops_log")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def sanitized_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    netloc = hostname
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def locust_version() -> str | None:
    try:
        return version("locust")
    except PackageNotFoundError:
        return None


def mysql_snapshot(args) -> dict:
    connection = pymysql.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version")
            mysql_version = cursor.fetchone()["version"]
            cursor.execute(
                "SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME IN (%s,%s,%s) "
                "ORDER BY TABLE_NAME",
                (args.db_name, *TABLES),
            )
            table_sizes = cursor.fetchall()
            exact_rows = {}
            for table in TABLES:
                cursor.execute(f"SELECT COUNT(*) AS row_count FROM `{table}`")
                exact_rows[table] = cursor.fetchone()["row_count"]
            cursor.execute(
                "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, CARDINALITY "
                "FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME IN (%s,%s,%s) "
                "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
                (args.db_name, *TABLES),
            )
            indexes = cursor.fetchall()
            cursor.execute(
                "SHOW GLOBAL STATUS WHERE Variable_name IN "
                "('Connections','Threads_connected','Threads_running','Questions','Slow_queries')"
            )
            status = {row["Variable_name"]: int(row["Value"]) for row in cursor.fetchall()}
    finally:
        connection.close()
    return {
        "version": mysql_version,
        "database": args.db_name,
        "exact_rows": exact_rows,
        "table_sizes": table_sizes,
        "indexes": indexes,
        "initial_status": status,
    }


def redis_snapshot(redis_url: str) -> dict:
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    server = client.info("server")
    memory = client.info("memory")
    stats = client.info("stats")
    key_count = sum(1 for pattern in ("omms:os:*", "omms:process:*", "omms:log_stats:*") for _ in client.scan_iter(match=pattern))
    config = client.config_get("maxmemory*")
    return {
        "endpoint": sanitized_url(redis_url),
        "version": server.get("redis_version"),
        "used_memory": memory.get("used_memory"),
        "keyspace_hits": stats.get("keyspace_hits"),
        "keyspace_misses": stats.get("keyspace_misses"),
        "monitor_cache_key_count": key_count,
        "config": config,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--db-host", default=os.getenv("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.getenv("DB_PORT", "3307")))
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", "omms_app"))
    parser.add_argument("--db-user", default=os.getenv("DB_USER", "omms"))
    parser.add_argument("--db-password", default=os.getenv("DB_PASSWORD", "omms_dev"))
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0"))
    parser.add_argument("--host", default="http://127.0.0.1:8004")
    parser.add_argument("--cache-scenario", choices=("warm", "expiry"), required=True)
    parser.add_argument("--users", required=True)
    args = parser.parse_args()

    snapshot = {
        "git": {
            "sha": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"),
            "dirty": bool(git("status", "--porcelain")),
        },
        "system": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpu_count": os.cpu_count(),
            "locust": locust_version(),
        },
        "workload": {
            "target": args.host,
            "cache_scenario": args.cache_scenario,
            "cache_ttl_seconds": int(os.getenv("OPS_CACHE_TTL_SECONDS", "3")),
            "users": args.users,
            "date": os.getenv("OMMS_BENCH_DATE", ""),
            "machine_tag": os.getenv("OMMS_BENCH_MACHINE_TAG", "fut-col-002"),
            "level": os.getenv("OMMS_BENCH_LEVEL", "error"),
        },
        "mysql": mysql_snapshot(args),
        "redis": redis_snapshot(args.redis_url),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
