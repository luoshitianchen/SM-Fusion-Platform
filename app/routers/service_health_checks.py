"""服务健康检查记录路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.health_check import HealthCheckCreate
from app.services.health_check import HealthCheckService

router = APIRouter(prefix="/api/fusion/health-checks", tags=["fusion-health-checks"])


@router.get("")
async def list_checks(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await HealthCheckService.list_checks(
        session, limit=limit, offset=offset,
        service_id=service_id, status_filter=status_filter, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_check(
    payload: HealthCheckCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await HealthCheckService.create_check(session, payload, request)


@router.get("/{check_id}")
async def get_check(
    check_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await HealthCheckService.get_check(session, check_id)
