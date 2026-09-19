"""服务依赖关系仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_dependency import ServiceDependency


async def get_dependency(session: AsyncSession, dep_id: str) -> ServiceDependency | None:
    result = await session.execute(select(ServiceDependency).where(ServiceDependency.id == dep_id))
    return result.scalar_one_or_none()


async def get_dependency_by_edge(
    session: AsyncSession, source: str, target: str, dep_type: str,
) -> ServiceDependency | None:
    result = await session.execute(
        select(ServiceDependency).where(
            ServiceDependency.source_service == source,
            ServiceDependency.target_service == target,
            ServiceDependency.dependency_type == dep_type,
        )
    )
    return result.scalar_one_or_none()


async def list_dependencies(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    source: str | None = None, target: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> list[ServiceDependency]:
    stmt = select(ServiceDependency).order_by(ServiceDependency.created_at.desc())
    if source:
        stmt = stmt.where(ServiceDependency.source_service == source)
    if target:
        stmt = stmt.where(ServiceDependency.target_service == target)
    if status:
        stmt = stmt.where(ServiceDependency.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(
            ServiceDependency.description.like(pattern),
            ServiceDependency.source_service.like(pattern),
            ServiceDependency.target_service.like(pattern),
        ))
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_dependencies(
    session: AsyncSession, source: str | None = None, target: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(ServiceDependency.id))
    if source:
        stmt = stmt.where(ServiceDependency.source_service == source)
    if target:
        stmt = stmt.where(ServiceDependency.target_service == target)
    if status:
        stmt = stmt.where(ServiceDependency.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(
            ServiceDependency.description.like(pattern),
            ServiceDependency.source_service.like(pattern),
            ServiceDependency.target_service.like(pattern),
        ))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_dependency(session: AsyncSession, dep: ServiceDependency) -> ServiceDependency:
    session.add(dep)
    await session.commit()
    await session.refresh(dep)
    return dep


async def update_dependency(session: AsyncSession, dep: ServiceDependency) -> ServiceDependency:
    await session.commit()
    await session.refresh(dep)
    return dep


async def delete_dependency(session: AsyncSession, dep: ServiceDependency) -> None:
    await session.delete(dep)
    await session.commit()
