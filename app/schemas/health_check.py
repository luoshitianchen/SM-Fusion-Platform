"""服务健康检查 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthCheckCreate(BaseModel):
    """记录一次健康探针结果。"""

    service_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    latency_ms: float = Field(default=0.0, ge=0.0, le=60000.0)
    endpoint: str = Field(default="", max_length=256)
    detail: str = Field(default="", max_length=2000)


class HealthCheckResponse(BaseModel):
    id: str
    service_id: str
    status: str
    latency_ms: float
    endpoint: str
    detail: str
    checked_at: str
    created_at: str


class HealthCheckListResponse(BaseModel):
    total: int
    items: list[HealthCheckResponse]
