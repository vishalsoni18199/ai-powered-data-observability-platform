"""Command-line helpers for demo ingestion and scheduled evaluation."""

import argparse
import json
from datetime import datetime, timezone

from .config import get_settings, load_registry
from .db import SessionLocal, initialize_database
from .schemas import RunIn
from .service import evaluate_pipeline
from .store import save_run


def main() -> None:
    parser = argparse.ArgumentParser(prog="obs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Create local metadata tables")
    ingest = sub.add_parser("ingest-run", help="Ingest one run record from JSON")
    ingest.add_argument("--json", required=True, help="JSON object matching the RunIn schema")
    check = sub.add_parser("evaluate", help="Run configured checks for every pipeline")
    check.add_argument("--pipeline-id")
    args = parser.parse_args()
    initialize_database()

    if args.command == "init-db":
        print("Database initialized")
        return
    if args.command == "ingest-run":
        payload = RunIn.model_validate_json(args.json)
        with SessionLocal() as session:
            row = save_run(session, payload.model_dump())
            print(json.dumps({"id": row.id, "pipeline_id": row.pipeline_id, "run_id": row.run_id}))
        return

    registry = load_registry(get_settings().config_path)
    pipelines = [p for p in registry.pipelines if not args.pipeline_id or p.pipeline_id == args.pipeline_id]
    if not pipelines:
        raise SystemExit("No matching pipelines found in CONFIG_PATH")
    with SessionLocal() as session:
        for pipeline in pipelines:
            print(json.dumps(evaluate_pipeline(session, pipeline), default=str))
