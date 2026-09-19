"""SLA 合规记录模型：按服务+周期统计可用性与合规状态。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class SLACompliance(Base):
    """SLA 合规记录：同一服务同一周期唯一。"""

    __tablename__ = "sla_compliance"
    __table_args__ = (
        UniqueConstraint("service_id", "period", name="uq_sla_service_period"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 统计周期，形如 2026-09
    period: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    availability_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    incident_count: Mapped[int] = mapped_column(Integer, default=0)
    # 合规状态：met / breached
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="met", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
