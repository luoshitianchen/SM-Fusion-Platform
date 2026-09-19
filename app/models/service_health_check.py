"""服务健康检查记录模型：记录单次健康探针的结果。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class ServiceHealthCheck(Base):
    """单次健康探针记录：一个服务可有多条历史记录。"""

    __tablename__ = "service_health_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 探针状态：healthy / degraded / unhealthy
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="healthy", index=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    endpoint: Mapped[str] = mapped_column(String(256), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
