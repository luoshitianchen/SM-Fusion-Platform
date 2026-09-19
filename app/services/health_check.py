"""服务健康检查记录服务层：探针记录生命周期管理。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.service_health_check import ServiceHealthCheck
from app.repositories import service_health_check as repo
from app.schemas.health_check import HealthCheckCreate
from app.services.audit import record_audit

# 允许的状态迁移（状态机）：healthy/degraded/unhealthy 任意方向均允许（含恢复）
_ALLOWED_TRANSITIONS = {
    "healthy": {"degraded", "unhealthy"},
    "degraded": {"healthy", "unhealthy"},
    "unhealthy": {"healthy", "degraded"},
}


def _check_to_dict(c: ServiceHealthCheck) -> dict:
    return {
        "id": c.id, "service_id": c.service_id, "status": c.status,
        "latency_ms": c.latency_ms, "endpoint": c.endpoint, "detail": c.detail,
        "checked_at": c.checked_at.isoformat() if c.checked_at else "",
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }


class HealthCheckService:
    @staticmethod
    async def list_checks(
        session: AsyncSession, limit: int, offset: int,
        service_id: str | None, status_filter: str | None, keyword: str | None,
    ) -> dict:
        items = await repo.list_checks(
            session, limit=limit, offset=offset,
            service_id=service_id, status=status_filter, keyword=keyword,
        )
        total = await repo.count_checks(
            session, service_id=service_id, status=status_filter, keyword=keyword,
        )
        return {"total": total, "items": [_check_to_dict(c) for c in items]}

    @staticmethod
    async def get_check(session: AsyncSession, check_id: str) -> dict:
        check = await repo.get_check(session, check_id)
        if not check:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "健康检查记录不存在")
        return _check_to_dict(check)

    @staticmethod
    async def create_check(session: AsyncSession, payload: HealthCheckCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        check = ServiceHealthCheck(
            id=str(uuid.uuid4()),
            service_id=payload.service_id,
            status=payload.status,
            latency_ms=payload.latency_ms,
            endpoint=payload.endpoint,
            detail=payload.detail,
            checked_at=datetime.now(UTC),
        )
        check = await repo.create_check(session, check)
        await record_audit(session, "health_check.recorded", "internal",
                           f"service_id={payload.service_id} status={payload.status}", request)
        return _check_to_dict(check)
