# -*- coding: utf-8 -*-
import random
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from app.models.ops_model import OpsCfg
from app.services.mq_consumer import ROUTING_LOG, ROUTING_STATE
from scripts.generate_data import build_logs, generate_configs
from scripts.mock_data import machine_tags
from scripts.mq_producer import build_message, build_properties, validate_generation

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_producer_messages(count=9):
    rng = random.Random(42)
    machines = machine_tags(3, seed=42)
    return [
        build_message(rng, machines, "20260822", 42, "both", index)
        for index in range(count)
    ]


def test_both_mode_round_robins_os_process_and_log():
    generated = build_producer_messages(9)
    categories = [
        message.get("type", "log")
        for message, _routing_key in generated
    ]
    routing_keys = [routing_key for _message, routing_key in generated]

    assert categories == ["os", "process", "log"] * 3
    assert routing_keys == [ROUTING_STATE, ROUTING_STATE, ROUTING_LOG] * 3


def test_both_mode_rejects_count_too_small_for_full_coverage():
    with pytest.raises(ValueError, match="至少需要"):
        validate_generation("both", 2)


@pytest.mark.parametrize("module", ["scripts.mq_producer", "scripts.generate_data"])
def test_module_cli_help_starts_from_repository_root(module):
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_producer_generation_is_reproducible_with_unique_log_event_ids():
    first = build_producer_messages(12)
    second = build_producer_messages(12)
    assert first == second

    logs = [message for message, _routing_key in first if message["kind"] == "log"]
    event_ids = [message["event_id"] for message in logs]
    assert len(event_ids) == len(set(event_ids))
    assert all(build_properties(message).message_id == message["event_id"] for message in logs)


def test_generate_configs_twice_does_not_duplicate_rows():
    engine = create_engine("sqlite:///:memory:")
    OpsCfg.__table__.create(engine)
    machines = machine_tags(3, seed=42)

    with engine.begin() as connection:
        generate_configs(connection, machines)
        generate_configs(connection, machines)
        count = connection.scalar(select(func.count()).select_from(OpsCfg))

    assert count == len(machines) * 4


def test_benchmark_logs_have_stable_unique_event_ids():
    machines = machine_tags(3, seed=42)
    namespace = uuid.UUID("12345678-1234-5678-1234-567812345678")
    first = build_logs(random.Random(42), machines, 9, "20260822", namespace)
    second = build_logs(random.Random(42), machines, 9, "20260822", namespace)

    assert first == second
    assert len({message["event_id"] for message in first}) == len(first)
