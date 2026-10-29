# AI-Powered Data Observability Platform

A modular MVP aligned to the dissertation scope: Oracle → Sqoop → Impala; freshness and quality checks; historical anomaly detection; explainable likely-cause ranking; SMTP email alerts; and Power BI API feeds.

## What is implemented

- FastAPI ingestion endpoints for Sqoop run metadata and custom metrics.
- SQLite metadata store for local execution; reference Impala DDL is in `sql/impala_schema.sql`.
- Configurable read-only Impala scalar checks in `config/pipelines.yaml`.
- Freshness SLA evaluation and data quality thresholds.
- Median/MAD anomaly detection for small histories and scikit-learn Isolation Forest after 30 observations.
- Heuristic root-cause ranking. Probabilities are prioritization scores, not calibrated model probabilities.
- SMTP email delivery when configured.
- Power BI friendly JSON endpoints for observations and runs.
- API key protection for write, evaluation, and incident endpoints.

## Local setup

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -e .
cp .env.example .env
obs init-db
uvicorn data_observability.api:app --reload
```

Open `http://127.0.0.1:8000/docs`. The local default API key is `change-me-before-deployment`; send it as `X-API-Key`.

In another terminal, ingest the sample run:

```bash
obs ingest-run --json "$(cat sample/run.json)"
```

On Windows PowerShell:

```powershell
$body = Get-Content sample/run.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/runs -Headers @{"X-API-Key"="change-me-before-deployment"} -ContentType "application/json" -Body $body
```

## Connect to Impala

Set the following in `.env`/deployment secrets:

```text
IMPALA_HOST=your-impala-coordinator
IMPALA_PORT=21050
IMPALA_DATABASE=analytics
IMPALA_USER=...
IMPALA_PASSWORD=...
IMPALA_AUTH_MECHANISM=PLAIN
```

Configure a real pipeline table and read-only queries in `config/pipelines.yaml`, then run:

```bash
obs evaluate --pipeline-id oracle_sales_to_impala
```

Freshness queries must return a single Unix epoch timestamp in seconds. Each quality query must return exactly one numeric value. Threshold operators accepted: `<`, `<=`, `>`, `>=`, `==`, `!=`. Use only SELECT queries and grant the service account read access to monitored objects.

## Sqoop integration

Configure the Sqoop/Oozie wrapper to POST one JSON document per run to `POST /v1/runs`. Include stable `run_id`, status, timestamps, counts and duration. A generic sample payload is in `sample/run.json`. Avoid sending credentials or raw business data in telemetry.

```bash
curl -X POST http://localhost:8000/v1/runs \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me-before-deployment' \
  --data @sample/run.json
```

## Power BI

Use **Get Data → Web** against these endpoints, passing `X-API-Key` through the connector's HTTP headers:

- `/v1/powerbi/runs`
- `/v1/powerbi/observations`
- `/v1/incidents`

For a managed Power BI Service deployment, put the API behind an approved gateway and configure credential rotation. Do not embed the API key in a report shared with broad audiences.

## Production hardening required

This is an implementation starter, not a plug-and-play enterprise deployment. Before production, configure TLS/reverse proxy, secrets manager, identity-based auth, SMTP relay, durable shared database, retention/partition lifecycle, retries, audit logs, idempotent alert suppression, and cluster-specific Impala/Kerberos/TLS settings. The included local persistence is SQLite; `sql/impala_schema.sql` documents the target metadata shape but is not a drop-in SQLAlchemy Impala backend. Validate all configured queries and thresholds with the Oracle/Impala owners. Add calibrated model evaluation with labeled incidents before treating anomaly scores as an accuracy claim.

## Proposed deployment shape

- Sqoop/Oozie completion hook submits run telemetry.
- This service persists metadata and evaluates configured SQL against Impala.
- Daily scheduler calls `obs evaluate` or the evaluation API endpoint.
- Power BI consumes API feeds for operational dashboards.

## Main API

- `GET /health`
- `POST /v1/runs`
- `POST /v1/metrics`
- `POST /v1/pipelines/{pipeline_id}/evaluate`
- `GET /v1/incidents?pipeline_id=...&status=open`
- `PATCH /v1/incidents/{id}`
- `GET /v1/powerbi/runs`
- `GET /v1/powerbi/observations`
