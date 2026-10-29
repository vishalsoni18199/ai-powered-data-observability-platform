"""FastAPI application exposing ingestion, evaluation, incidents, and Power BI feeds."""

import json
import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .config import get_settings, load_registry
from .db import SessionLocal, initialize_database
from .models import Incident, Observation, PipelineRun
from .schemas import IncidentStatusIn, MetricIn, RunIn
from .service import evaluate_pipeline
from .store import add_observation, save_run

app = FastAPI(title="Data Observability Platform", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def authorize(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().api_key
    if get_settings().app_env != "local" and expected == "change-me-before-deployment":
        raise HTTPException(status_code=503, detail="Set API_KEY before non-local deployment")
    if not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


SessionDep = Annotated[Session, Depends(get_session)]
AuthDep = Annotated[None, Depends(authorize)]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "data-observability-platform"}


@app.post("/v1/runs", dependencies=[Depends(authorize)])
def ingest_run(payload: RunIn, session: SessionDep) -> dict:
    run = save_run(session, payload.model_dump())
    if run.rows_written is not None:
        add_observation(session, run.pipeline_id, "rows_written", float(run.rows_written), run.finished_at or run.started_at, {"run_id": run.run_id})
    if run.duration_seconds is not None:
        add_observation(session, run.pipeline_id, "duration_seconds", run.duration_seconds, run.finished_at or run.started_at, {"run_id": run.run_id})
    return {"id": run.id, "pipeline_id": run.pipeline_id, "run_id": run.run_id, "status": run.status}


@app.post("/v1/metrics", dependencies=[Depends(authorize)])
def ingest_metric(payload: MetricIn, session: SessionDep) -> dict:
    record = add_observation(
        session,
        payload.pipeline_id,
        payload.metric_name,
        payload.metric_value,
        payload.observed_at or datetime.now(timezone.utc),
        payload.details,
    )
    return {"id": record.id, "accepted": True}


@app.post("/v1/pipelines/{pipeline_id}/evaluate", dependencies=[Depends(authorize)])
def evaluate(pipeline_id: str, session: SessionDep) -> dict:
    registry = load_registry(get_settings().config_path)
    try:
        pipeline = registry.by_id(pipeline_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return evaluate_pipeline(session, pipeline)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Evaluation failed: {exc}") from exc


@app.get("/v1/incidents", dependencies=[Depends(authorize)])
def list_incidents(
    session: SessionDep,
    pipeline_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    query = select(Incident).order_by(desc(Incident.created_at)).limit(limit)
    if pipeline_id:
        query = query.where(Incident.pipeline_id == pipeline_id)
    if status:
        query = query.where(Incident.status == status)
    rows = session.scalars(query)
    return [_incident_dict(row) for row in rows]


@app.patch("/v1/incidents/{incident_id}", dependencies=[Depends(authorize)])
def update_incident(incident_id: int, payload: IncidentStatusIn, session: SessionDep) -> dict:
    row = session.get(Incident, incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    row.status = payload.status
    session.commit()
    return _incident_dict(row)


@app.get("/v1/powerbi/observations", dependencies=[Depends(authorize)])
def powerbi_observations(session: SessionDep, limit: int = Query(default=5000, ge=1, le=50000)) -> list[dict]:
    rows = session.scalars(select(Observation).order_by(desc(Observation.observed_at)).limit(limit))
    return [
        {"pipeline_id": row.pipeline_id, "metric_name": row.metric_name,
         "metric_value": row.metric_value, "observed_at": row.observed_at.isoformat(),
         "details": json.loads(row.details_json)}
        for row in rows
    ]


@app.get("/v1/powerbi/runs", dependencies=[Depends(authorize)])
def powerbi_runs(session: SessionDep, limit: int = Query(default=5000, ge=1, le=50000)) -> list[dict]:
    rows = session.scalars(select(PipelineRun).order_by(desc(PipelineRun.started_at)).limit(limit))
    return [
        {"pipeline_id": row.pipeline_id, "run_id": row.run_id, "status": row.status,
         "started_at": row.started_at.isoformat(),
         "finished_at": row.finished_at.isoformat() if row.finished_at else None,
         "rows_read": row.rows_read, "rows_written": row.rows_written,
         "duration_seconds": row.duration_seconds, "source": row.source}
        for row in rows
    ]


def _incident_dict(row: Incident) -> dict:
    return {
        "id": row.id, "pipeline_id": row.pipeline_id, "run_id": row.run_id,
        "rule_name": row.rule_name, "severity": row.severity, "title": row.title,
        "details": row.details, "probable_causes": json.loads(row.probable_causes_json),
        "status": row.status, "created_at": row.created_at.isoformat(),
    }
