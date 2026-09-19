"""SLA 合规记录服务层：周期可用性统计与合规判定。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.sla_compliance import SLACompliance
from app.repositories import sla_compliance as repo
from app.schemas.sla import SLACreate, SLAUpdate
from app.services.audit import record_audit

# SLO 阈值：可用性低于该值视为违约
SLO_THRESHOLD_PCT = 99.9


def _derive_status(availability_pct: float) -> str:
    """根据可用性推导合规状态。"""
    return "met" if availability_pct >= SLO_THRESHOLD_PCT else "breached"


def _sla_to_dict(r: SLACompliance) -> dict:
    return {
        "id": r.id, "service_id": r.service_id, "period": r.period,
        "availability_pct": r.availability_pct, "incident_count": r.incident_count,
        "status": r.status, "note": r.note,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


class SLAService:
    @staticmethod
    async def list_records(
        session: AsyncSession, limit: int, offset: int,
        service_id: str | None, status_filter: str | None, keyword: str | None,
    ) -> dict:
        items = await repo.list_records(
            session, limit=limit, offset=offset,
            service_id=service_id, status=status_filter, keyword=keyword,
        )
        total = await repo.count_records(
            session, service_id=service_id,
            status=status_filter, keyword=keyword,
        )
        return {"total": total, "items": [_sla_to_dict(r) for r in items]}

    @staticmethod
    async def get_record(session: AsyncSession, record_id: str) -> dict:
        record = await repo.get_record(session, record_id)
        if not record:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA 记录不存在")
        return _sla_to_dict(record)

    @staticmethod
    async def create_record(session: AsyncSession, payload: SLACreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_record_by_service_period(session, payload.service_id, payload.period):
            raise HTTPException(status.HTTP_409_CONFLICT, "该服务此周期的 SLA 记录已存在")
        record = SLACompliance(
            id=str(uuid.uuid4()),
            service_id=payload.service_id,
            period=payload.period,
            availability_pct=payload.availability_pct,
            incident_count=payload.incident_count,
            status=_derive_status(payload.availability_pct),
            note=payload.note,
        )
        record = await repo.create_record(session, record)
        await record_audit(session, "sla.recorded", "internal",
                           f"service_id={payload.service_id} period={payload.period} status={record.status}",
                           request)
        return _sla_to_dict(record)

    @staticmethod
    async def update_record(
        session: AsyncSession, record_id: str, payload: SLAUpdate, request: Request,
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        record = await repo.get_record(session, record_id)
        if not record:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA 记录不存在")
        if payload.availability_pct is not None:
            record.availability_pct = payload.availability_pct
            record.status = _derive_status(payload.availability_pct)
        if payload.incident_count is not None:
            record.incident_count = payload.incident_count
        if payload.note is not None:
            record.note = payload.note
        record = await repo.update_record(session, record)
        await record_audit(session, "sla.updated", "internal", f"id={record_id}", request)
        return _sla_to_dict(record)

    @staticmethod
    async def delete_record(session: AsyncSession, record_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        record = await repo.get_record(session, record_id)
        if not record:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA 记录不存在")
        await repo.delete_record(session, record)
        await record_audit(session, "sla.deleted", "internal", f"id={record_id}", request)
        return {"deleted": True, "id": record_id}
