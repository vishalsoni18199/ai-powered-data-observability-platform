"""Application and pipeline configuration."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./observability.db"
    api_key: str = "change-me-before-deployment"
    config_path: str = "./config/pipelines.yaml"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "observability@example.com"
    smtp_to: str = "data-engineering@example.com"
    smtp_starttls: bool = True
    impala_host: str | None = None
    impala_port: int = 21050
    impala_database: str = "default"
    impala_user: str | None = None
    impala_password: str | None = None
    impala_auth_mechanism: str = "PLAIN"


class SqlCheck(BaseModel):
    name: str
    sql: str = Field(description="Read-only Impala SQL returning one numeric value")
    metric: str
    operator: str = "<="
    threshold: float = 0
    severity: str = "critical"


class PipelineConfig(BaseModel):
    pipeline_id: str
    description: str = ""
    expected_interval_minutes: int = 1440
    freshness_timestamp_sql: str | None = None
    row_count_sql: str | None = None
    quality_checks: list[SqlCheck] = Field(default_factory=list)
    recipients: list[str] = []


class PipelineRegistry(BaseModel):
    pipelines: list[PipelineConfig]

    def by_id(self, pipeline_id: str) -> PipelineConfig:
        for pipeline in self.pipelines:
            if pipeline.pipeline_id == pipeline_id:
                return pipeline
        raise KeyError(f"Unknown pipeline_id: {pipeline_id}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def load_registry(path: str | Path) -> PipelineRegistry:
    config_path = Path(path)
    if not config_path.exists():
        return PipelineRegistry(pipelines=[])
    with config_path.open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream) or {"pipelines": []}
    return PipelineRegistry.model_validate(payload)
