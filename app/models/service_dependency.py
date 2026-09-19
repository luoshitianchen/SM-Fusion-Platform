"""服务依赖关系模型：刻画服务间同步/异步调用拓扑。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class ServiceDependency(Base):
    """服务依赖边：source_service -> target_service，按类型唯一。"""

    __tablename__ = "service_dependencies"
    __table_args__ = (
        UniqueConstraint("source_service", "target_service", "dependency_type", name="uq_dependency_edge"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_service: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_service: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 依赖类型：sync（同步调用）/ async（事件异步）
    dependency_type: Mapped[str] = mapped_column(String(16), nullable=False, default="sync")
    # 拓扑状态：active / broken
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
