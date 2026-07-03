"""OpsFlow AI command-line interface.

P0 flow:
    python -m opsflow generate-events --count 1000 --scenario ocr_failure_spike --output sample_data/events.jsonl
    python -m opsflow detect-anomalies --input sample_data/events.jsonl --output sample_data/anomalies.json
    python -m opsflow diagnose --input sample_data/anomalies.json --events sample_data/events.jsonl --output reports/incident_report.md
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click

from opsflow import __version__, config
from opsflow.data_gen.generator import EventGenerator, read_events_jsonl, write_events_jsonl
from opsflow.data_gen.scenarios import SCENARIOS
from opsflow.detection.anomaly_detector import (
    DetectorConfig,
    detect_anomalies,
    write_anomalies_json,
)
from opsflow.rca.diagnosis_agent import DiagnosisAgent
from opsflow.rca.report_writer import write_report


@click.group()
@click.version_option(version=__version__, prog_name="opsflow")
def main() -> None:
    """OpsFlow AI — synthetic operational data platform."""


@main.command("generate-events")
@click.option("--count", default=config.DEFAULT_EVENT_COUNT, show_default=True, help="Number of events to generate.")
@click.option("--scenario", default="ocr_failure_spike", show_default=True, type=click.Choice(sorted(SCENARIOS)), help="Anomaly scenario to inject.")
@click.option("--output", default=config.DEFAULT_EVENTS_PATH, show_default=True, type=click.Path(path_type=Path))
@click.option("--seed", default=config.DEFAULT_SEED, show_default=True, help="Random seed (deterministic output).")
@click.option("--duration-minutes", default=config.DEFAULT_DURATION_MINUTES, show_default=True, help="Timespan the events cover.")
@click.option("--start-time", default=None, help="ISO-8601 start of the timespan (default: now - duration). Useful for reproducible runs.")
def generate_events(count: int, scenario: str, output: Path, seed: int, duration_minutes: int, start_time: str | None) -> None:
    """Generate synthetic operational events as JSONL."""
    parsed_start = datetime.fromisoformat(start_time) if start_time else None
    generator = EventGenerator(
        seed=seed,
        scenario=scenario,
        start_time=parsed_start,
        duration_minutes=duration_minutes,
    )
    events = generator.generate(count)
    write_events_jsonl(events, output)
    injected = sum(1 for e in events if e.metadata.get("injected_anomaly"))
    click.echo(
        f"Wrote {len(events)} events to {output} "
        f"(scenario={scenario}, seed={seed}, injected anomalous events={injected})"
    )


@main.command("detect-anomalies")
@click.option("--input", "input_path", default=config.DEFAULT_EVENTS_PATH, show_default=True, type=click.Path(exists=True, path_type=Path))
@click.option("--output", default=config.DEFAULT_ANOMALIES_PATH, show_default=True, type=click.Path(path_type=Path))
@click.option("--bucket-minutes", default=DetectorConfig.bucket_minutes, show_default=True)
@click.option("--z-threshold", default=DetectorConfig.z_threshold, show_default=True)
@click.option("--min-failure-rate", default=DetectorConfig.min_failure_rate, show_default=True)
def detect_anomalies_cmd(input_path: Path, output: Path, bucket_minutes: int, z_threshold: float, min_failure_rate: float) -> None:
    """Detect anomaly windows in an event stream (baseline vs spike, robust z-score)."""
    events = read_events_jsonl(input_path)
    detector_config = DetectorConfig(
        bucket_minutes=bucket_minutes,
        z_threshold=z_threshold,
        min_failure_rate=min_failure_rate,
    )
    result = detect_anomalies(events, detector_config)
    result["source"] = str(input_path)
    write_anomalies_json(result, output)
    click.echo(
        f"Analyzed {len(events)} events in {result['bucket_count']} buckets: "
        f"{len(result['anomalies'])} anomaly window(s) found. Wrote {output}"
    )
    for anomaly in result["anomalies"]:
        click.echo(
            f"  {anomaly['anomaly_id']} [{anomaly['severity']}] "
            f"{anomaly['window_start']} → {anomaly['window_end']} "
            f"failure_rate={anomaly['metrics']['failure_rate']:.1%}"
        )


@main.command("diagnose")
@click.option("--input", "anomalies_path", default=config.DEFAULT_ANOMALIES_PATH, show_default=True, type=click.Path(exists=True, path_type=Path))
@click.option("--events", "events_path", default=config.DEFAULT_EVENTS_PATH, show_default=True, type=click.Path(exists=True, path_type=Path))
@click.option("--output", default=config.DEFAULT_REPORT_PATH, show_default=True, type=click.Path(path_type=Path))
def diagnose(anomalies_path: Path, events_path: Path, output: Path) -> None:
    """Run the deterministic RCA workflow and write a Markdown incident report."""
    agent = DiagnosisAgent()
    diagnoses = agent.diagnose_file(anomalies_path, events_path)
    write_report(diagnoses, output, str(events_path), str(anomalies_path))
    click.echo(f"Diagnosed {len(diagnoses)} anomaly window(s). Report: {output}")
    for d in diagnoses:
        click.echo(
            f"  {d.anomaly['anomaly_id']}: confidence={d.hypothesis['confidence']} — "
            f"{d.hypothesis['hypothesis'][:100]}..."
        )


@main.command("ingest")
@click.option("--input", "input_path", default=config.DEFAULT_EVENTS_PATH, show_default=True, type=click.Path(exists=True, path_type=Path))
@click.option("--batch-size", default=500, show_default=True, help="Rows per insert batch.")
def ingest(input_path: Path, batch_size: int) -> None:
    """Load events JSONL into Postgres (idempotent: ON CONFLICT DO NOTHING)."""
    try:
        import psycopg  # noqa: F401
    except ImportError as exc:
        raise click.ClickException(
            "psycopg is not installed. Install the P1 extra: pip install -e '.[postgres]'"
        ) from exc

    from opsflow.db.connection import DbSettings, connect
    from opsflow.ingestion.postgres_loader import apply_schema, ingest_events

    events = read_events_jsonl(input_path)
    settings = DbSettings.from_env()
    try:
        with connect(settings) as conn:
            apply_schema(conn)
            result = ingest_events(conn, events, batch_size=batch_size)
    except Exception as exc:  # OperationalError etc. — give an actionable message
        raise click.ClickException(
            f"Could not ingest into Postgres at {settings.host}:{settings.port}/"
            f"{settings.dbname}: {exc}\nIs the database up? Try: docker compose up -d"
        ) from exc

    click.echo(
        f"Ingested {input_path}: rows read={result.rows_read}, "
        f"inserted={result.rows_inserted}, skipped (duplicates)={result.rows_skipped}"
    )


if __name__ == "__main__":
    main()
