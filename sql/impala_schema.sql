-- Reference Impala DDL for production metadata persistence.
-- The runnable starter defaults to SQLite so it can be evaluated locally without cluster access.
CREATE DATABASE IF NOT EXISTS observability;

CREATE TABLE IF NOT EXISTS observability.pipeline_runs (
  pipeline_id STRING,
  run_id STRING,
  status STRING,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  rows_read BIGINT,
  rows_written BIGINT,
  duration_seconds DOUBLE,
  source STRING,
  error_message STRING,
  created_at TIMESTAMP
)
STORED AS PARQUET;

CREATE TABLE IF NOT EXISTS observability.observations (
  pipeline_id STRING,
  metric_name STRING,
  metric_value DOUBLE,
  observed_at TIMESTAMP,
  details_json STRING
)
PARTITIONED BY (observation_date STRING)
STORED AS PARQUET;

CREATE TABLE IF NOT EXISTS observability.incidents (
  pipeline_id STRING,
  run_id STRING,
  rule_name STRING,
  severity STRING,
  title STRING,
  details STRING,
  probable_causes_json STRING,
  status STRING,
  created_at TIMESTAMP
)
PARTITIONED BY (incident_date STRING)
STORED AS PARQUET;
