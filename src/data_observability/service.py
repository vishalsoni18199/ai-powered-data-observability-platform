"""Evaluation orchestration for submitted pipeline telemetry and configured checks."""

import json
import smtplib
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .alerts import send_incident_email
from .anomaly import AnomalyDetector
from .config import PipelineConfig
from .impala import ImpalaClient
from .models import Incident, Observation
from .rca import rank_causes
from .store import create_incident, history, recent_runs


def _record_incident(
    session: Session,
    pipeline: PipelineConfig,
    rule_name: str,
    metric_name: str,
    value: float,
    severity: str,
    details: dict,
) -> Incident:
    causes = rank_causes(rule_name, metric_name, recent_runs(session, pipeline.pipeline_id), details)
    incident = create_incident(
        session,
        pipeline_id=pipeline.pipeline_id,
        run_id=details.get("run_id"),
        rule_name=rule_name,
        severity=severity,
        title=f"{pipeline.pipeline_id}: {rule_name}",
        details=json.dumps({"metric": metric_name, "value": value, **details}, default=str),
        probable_causes_json=json.dumps(causes),
    )
    try:
        send_incident_email(incident, pipeline.recipients)
    except (OSError, smtplib.SMTPException) as exc:
        incident.details += f"\nEmail delivery error: {exc}"
        session.commit()
    return incident


def evaluate_pipeline(session: Session, pipeline: PipelineConfig, impala: ImpalaClient | None = None) -> dict:
    """Run configured read-only checks and evaluate metrics against their baseline."""
    client = impala or ImpalaClient()
    emitted: list[dict] = []
    now = datetime.now(timezone.utc)
    for check in pipeline.quality_checks:
        try:
            value = client.scalar(check.sql)
        except RuntimeError:
            # Local demo can still ingest and evaluate submitted telemetry without Impala.
            continue
        observation = Observation(
            pipeline_id=pipeline.pipeline_id,
            metric_name=check.metric,
            metric_value=value,
            observed_at=now,
            details_json="{}",
        )
        session.add(observation)
        session.commit()
        failed = _compare(value, check.operator, check.threshold)
        prior = history(session, pipeline.pipeline_id, check.metric)
        anomaly = AnomalyDetector().score(prior[:-1], value)
        if failed or anomaly["is_anomaly"]:
            reason = "threshold_violation" if failed else "historical_anomaly"
            incident = _record_incident(
                session,
                pipeline,
                check.name,
                check.metric,
                value,
                check.severity,
                {"reason": reason, "threshold": check.threshold, "anomaly": anomaly},
            )
            emitted.append({"incident_id": incident.id, "rule": check.name, "reason": reason})

    # Freshness uses epoch seconds returned by the configured Impala query.
    if pipeline.freshness_timestamp_sql:
        timestamp = client.scalar(pipeline.freshness_timestamp_sql)
        age_minutes = max(0.0, (now.timestamp() - timestamp) / 60.0)
        session.add(Observation(
            pipeline_id=pipeline.pipeline_id,
            metric_name="freshness_age_minutes",
            metric_value=age_minutes,
            observed_at=now,
            details_json="{}",
        ))
        session.commit()
        if age_minutes > pipeline.expected_interval_minutes:
            incident = _record_incident(
                session, pipeline, "freshness_sla", "freshness_age_minutes", age_minutes,
                "critical", {"expected_interval_minutes": pipeline.expected_interval_minutes},
            )
            emitted.append({"incident_id": incident.id, "rule": "freshness_sla", "reason": "stale_data"})
    return {"pipeline_id": pipeline.pipeline_id, "evaluated_at": now.isoformat(), "incidents": emitted}


def _compare(value: float, operator: str, threshold: float) -> bool:
    comparisons = {
        "<": value < threshold,
        "<=": value <= threshold,
        ">": value > threshold,
        ">=": value >= threshold,
        "==": value == threshold,
        "!=": value != threshold,
    }
    if operator not in comparisons:
        raise ValueError(f"Unsupported comparison operator: {operator}")
    return comparisons[operator]
