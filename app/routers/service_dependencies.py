"""服务依赖关系路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.dependency import DependencyCreate, DependencyStatusUpdate, DependencyUpdate
from app.services.service_dependency import DependencyService

router = APIRouter(prefix="/api/fusion/dependencies", tags=["fusion-dependencies"])


@router.get("")
async def list_dependencies(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source: str | None = Query(default=None),
    target: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await DependencyService.list_dependencies(
        session, limit=limit, offset=offset,
        source=source, target=target,
        status_filter=status_filter, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_dependency(
    payload: DependencyCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await DependencyService.create_dependency(session, payload, request)


@router.get("/{dep_id}")
async def get_dependency(
    dep_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await DependencyService.get_dependency(session, dep_id)


@router.patch("/{dep_id}")
async def update_dependency(
    dep_id: str, payload: DependencyUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await DependencyService.update_dependency(session, dep_id, payload, request)


@router.patch("/{dep_id}/status")
async def update_dependency_status(
    dep_id: str, payload: DependencyStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await DependencyService.update_status(session, dep_id, payload.status, request)


@router.delete("/{dep_id}")
async def delete_dependency(
    dep_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await DependencyService.delete_dependency(session, dep_id, request)
