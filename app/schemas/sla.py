"""SLA 合规记录 Pydantic 模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SLACreate(BaseModel):
    service_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    # 周期形如 2026-09
    period: str = Field(min_length=7, max_length=16, pattern=r"^\d{4}-\d{2}$")
    availability_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    incident_count: int = Field(default=0, ge=0, le=100000)
    note: str = Field(default="", max_length=1000)


class SLAUpdate(BaseModel):
    availability_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    incident_count: int | None = Field(default=None, ge=0, le=100000)
    note: str | None = Field(default=None, max_length=1000)


class SLAResponse(BaseModel):
    id: str
    service_id: str
    period: str
    availability_pct: float
    incident_count: int
    status: str
    note: str
    created_at: str
    updated_at: str


class SLAListResponse(BaseModel):
    total: int
    items: list[SLAResponse]
