"""Explainable heuristic ranking for likely operational causes."""


def rank_causes(rule_name: str, metric_name: str, recent_runs: list, details: dict | None = None) -> list[dict]:
    details = details or {}
    scores = {
        "upstream_source_delay": 0.10,
        "schema_or_contract_change": 0.05,
        "sqoop_transfer_or_network_issue": 0.05,
        "target_quality_regression": 0.05,
        "compute_or_resource_pressure": 0.05,
    }
    failed = sum(1 for run in recent_runs[:5] if run.status == "failed")
    if "freshness" in rule_name or "freshness" in metric_name:
        scores["upstream_source_delay"] += 0.55
    if "schema" in rule_name or "schema" in metric_name:
        scores["schema_or_contract_change"] += 0.65
    if "row_count" in metric_name or "volume" in metric_name:
        scores["sqoop_transfer_or_network_issue"] += 0.25
        scores["upstream_source_delay"] += 0.15
    if "null" in metric_name or "quality" in rule_name:
        scores["target_quality_regression"] += 0.50
    if failed:
        scores["sqoop_transfer_or_network_issue"] += min(0.35, 0.1 * failed)
    if details.get("duration_seconds"):
        scores["compute_or_resource_pressure"] += 0.15
    total = sum(scores.values()) or 1.0
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
    return [{"cause": name, "probability": round(score / total, 3)} for name, score in ranked]
