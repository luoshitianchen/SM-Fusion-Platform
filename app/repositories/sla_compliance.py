"""SLA 合规记录仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sla_compliance import SLACompliance


async def get_record(session: AsyncSession, record_id: str) -> SLACompliance | None:
    result = await session.execute(select(SLACompliance).where(SLACompliance.id == record_id))
    return result.scalar_one_or_none()


async def get_record_by_service_period(
    session: AsyncSession, service_id: str, period: str,
) -> SLACompliance | None:
    result = await session.execute(
        select(SLACompliance).where(
            SLACompliance.service_id == service_id,
            SLACompliance.period == period,
        )
    )
    return result.scalar_one_or_none()


async def list_records(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    service_id: str | None = None, status: str | None = None,
    keyword: str | None = None,
) -> list[SLACompliance]:
    stmt = select(SLACompliance).order_by(SLACompliance.period.desc(), SLACompliance.service_id)
    if service_id:
        stmt = stmt.where(SLACompliance.service_id == service_id)
    if status:
        stmt = stmt.where(SLACompliance.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(
            SLACompliance.note.like(pattern),
            SLACompliance.period.like(pattern),
        ))
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_records(
    session: AsyncSession, service_id: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(SLACompliance.id))
    if service_id:
        stmt = stmt.where(SLACompliance.service_id == service_id)
    if status:
        stmt = stmt.where(SLACompliance.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(
            SLACompliance.note.like(pattern),
            SLACompliance.period.like(pattern),
        ))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_record(session: AsyncSession, record: SLACompliance) -> SLACompliance:
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def update_record(session: AsyncSession, record: SLACompliance) -> SLACompliance:
    await session.commit()
    await session.refresh(record)
    return record


async def delete_record(session: AsyncSession, record: SLACompliance) -> None:
    await session.delete(record)
    await session.commit()
