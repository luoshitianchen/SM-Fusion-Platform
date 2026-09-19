"""SLA 合规记录路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.sla import SLACreate, SLAUpdate
from app.services.sla_compliance import SLAService

router = APIRouter(prefix="/api/fusion/sla", tags=["fusion-sla"])


@router.get("")
async def list_records(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SLAService.list_records(
        session, limit=limit, offset=offset,
        service_id=service_id, status_filter=status_filter, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_record(
    payload: SLACreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SLAService.create_record(session, payload, request)


@router.get("/{record_id}")
async def get_record(
    record_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SLAService.get_record(session, record_id)


@router.patch("/{record_id}")
async def update_record(
    record_id: str, payload: SLAUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SLAService.update_record(session, record_id, payload, request)


@router.delete("/{record_id}")
async def delete_record(
    record_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SLAService.delete_record(session, record_id, request)
