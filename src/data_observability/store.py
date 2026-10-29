"""Small repository layer keeping HTTP and evaluation code independent of SQLAlchemy."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .models import Incident, Observation, PipelineRun


def save_run(session: Session, data: dict) -> PipelineRun:
    existing = session.scalar(
        select(PipelineRun).where(
            PipelineRun.pipeline_id == data["pipeline_id"], PipelineRun.run_id == data["run_id"]
        )
    )
    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        session.commit()
        return existing
    record = PipelineRun(**data)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def add_observation(
    session: Session,
    pipeline_id: str,
    metric_name: str,
    metric_value: float,
    observed_at: datetime,
    details: dict,
) -> Observation:
    record = Observation(
        pipeline_id=pipeline_id,
        metric_name=metric_name,
        metric_value=metric_value,
        observed_at=observed_at,
        details_json=json.dumps(details, default=str),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def history(session: Session, pipeline_id: str, metric_name: str, days: int = 60) -> list[float]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.scalars(
        select(Observation.metric_value)
        .where(
            Observation.pipeline_id == pipeline_id,
            Observation.metric_name == metric_name,
            Observation.observed_at >= since,
        )
        .order_by(Observation.observed_at)
    )
    return list(rows)


def recent_runs(session: Session, pipeline_id: str, limit: int = 20) -> list[PipelineRun]:
    return list(
        session.scalars(
            select(PipelineRun)
            .where(PipelineRun.pipeline_id == pipeline_id)
            .order_by(desc(PipelineRun.started_at))
            .limit(limit)
        )
    )


def create_incident(session: Session, **data) -> Incident:
    row = Incident(**data)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
