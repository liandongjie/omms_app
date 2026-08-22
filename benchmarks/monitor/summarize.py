"""Extract the stable headline metrics from a Locust stats CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def build_summary(stats_path: Path, *, scenario: str, users: int) -> dict:
    with stats_path.open(encoding="utf-8-sig", newline="") as handle:
        aggregate = next(
            row for row in csv.DictReader(handle) if row.get("Name") == "Aggregated"
        )
    requests = int(aggregate["Request Count"])
    failures = int(aggregate["Failure Count"])
    return {
        "cache_scenario": scenario,
        "users": users,
        "request_count": requests,
        "failure_count": failures,
        "failure_rate_percent": round(failures * 100 / requests, 6) if requests else 0.0,
        "rps": float(aggregate["Requests/s"]),
        "p50_ms": float(aggregate["50%"]),
        "p95_ms": float(aggregate["95%"]),
        "p99_ms": float(aggregate["99%"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=("warm", "expiry"), required=True)
    parser.add_argument("--users", type=int, required=True)
    args = parser.parse_args()

    summary = build_summary(args.stats, scenario=args.scenario, users=args.users)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
