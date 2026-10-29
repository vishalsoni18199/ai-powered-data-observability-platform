"""HTTP request and response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RunIn(BaseModel):
    pipeline_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    status: Literal["success", "failed", "running"]
    started_at: datetime
    finished_at: datetime | None = None
    rows_read: int | None = Field(default=None, ge=0)
    rows_written: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    source: str = "sqoop"
    error_message: str | None = None


class MetricIn(BaseModel):
    pipeline_id: str
    metric_name: str
    metric_value: float
    observed_at: datetime | None = None
    details: dict[str, str | int | float | bool | None] = {}


class IncidentStatusIn(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
