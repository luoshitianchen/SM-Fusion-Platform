"""服务依赖关系 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DependencyCreate(BaseModel):
    source_service: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    target_service: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    dependency_type: Literal["sync", "async"] = "sync"
    description: str = Field(default="", max_length=1000)


class DependencyUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=1000)


class DependencyStatusUpdate(BaseModel):
    status: Literal["active", "broken"]


class DependencyResponse(BaseModel):
    id: str
    source_service: str
    target_service: str
    dependency_type: str
    status: str
    description: str
    created_at: str
    updated_at: str


class DependencyListResponse(BaseModel):
    total: int
    items: list[DependencyResponse]
