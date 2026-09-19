"""服务健康检查记录仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_health_check import ServiceHealthCheck


async def get_check(session: AsyncSession, check_id: str) -> ServiceHealthCheck | None:
    result = await session.execute(
        select(ServiceHealthCheck).where(ServiceHealthCheck.id == check_id)
    )
    return result.scalar_one_or_none()


async def list_checks(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    service_id: str | None = None, status: str | None = None,
    keyword: str | None = None,
) -> list[ServiceHealthCheck]:
    stmt = select(ServiceHealthCheck).order_by(ServiceHealthCheck.checked_at.desc())
    if service_id:
        stmt = stmt.where(ServiceHealthCheck.service_id == service_id)
    if status:
        stmt = stmt.where(ServiceHealthCheck.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(
            ServiceHealthCheck.detail.like(pattern),
            ServiceHealthCheck.endpoint.like(pattern),
        ))
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_checks(
    session: AsyncSession, service_id: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(ServiceHealthCheck.id))
    if service_id:
        stmt = stmt.where(ServiceHealthCheck.service_id == service_id)
    if status:
        stmt = stmt.where(ServiceHealthCheck.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(
            ServiceHealthCheck.detail.like(pattern),
            ServiceHealthCheck.endpoint.like(pattern),
        ))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_check(session: AsyncSession, check: ServiceHealthCheck) -> ServiceHealthCheck:
    session.add(check)
    await session.commit()
    await session.refresh(check)
    return check
