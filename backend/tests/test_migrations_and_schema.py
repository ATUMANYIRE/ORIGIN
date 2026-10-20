"""Tests for Alembic database migrations and complete schema verification."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_and_downgrade_cycle(tmp_path: Path) -> None:
    """Verify Alembic migrations upgrade to head, create all tables, and downgrade cleanly."""
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini = backend_dir / "alembic.ini"
    migration_db = tmp_path / "alembic_verify.db"
    async_url = f"sqlite+aiosqlite:///{migration_db}"
    sync_url = f"sqlite:///{migration_db}"

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", async_url)

    # Upgrade to head
    command.upgrade(cfg, "head")

    sync_engine = create_engine(sync_url)
    inspector = inspect(sync_engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "registered_systems",
        "services",
        "service_dependencies",
        "telemetry_sources",
        "metric_observations",
        "span_observations",
        "investigations",
        "experiment_definitions",
        "experiment_runs",
        "hypotheses",
        "evidence_records",
        "benchmark_runs",
        "audit_events",
        "digital_twin_models",
        "calibration_runs",
        "simulation_snapshots",
        "simulation_branches",
        "scientific_memory_entries",
        "recovery_plans",
        "remediation_candidates",
        "sandbox_verification_runs",
        "recovery_approvals",
        "recovery_executions",
        "recovery_rollbacks",
        "safety_policy_evaluations",
    }
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    # Verify downgrade to base removes application tables
    command.downgrade(cfg, "base")
    inspector_after = inspect(sync_engine)
    remaining = set(inspector_after.get_table_names()) - {"alembic_version"}
    assert len(remaining) == 0

    # Re-upgrade to head
    command.upgrade(cfg, "head")
    inspector_final = inspect(sync_engine)
    assert expected_tables.issubset(set(inspector_final.get_table_names()))
    sync_engine.dispose()
