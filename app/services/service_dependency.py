"""服务依赖关系服务层：依赖拓扑生命周期管理。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.service_dependency import ServiceDependency
from app.repositories import service_dependency as repo
from app.schemas.dependency import DependencyCreate, DependencyUpdate
from app.services.audit import record_audit


def _dep_to_dict(d: ServiceDependency) -> dict:
    return {
        "id": d.id, "source_service": d.source_service,
        "target_service": d.target_service, "dependency_type": d.dependency_type,
        "status": d.status, "description": d.description,
        "created_at": d.created_at.isoformat() if d.created_at else "",
        "updated_at": d.updated_at.isoformat() if d.updated_at else "",
    }


class DependencyService:
    @staticmethod
    async def list_dependencies(
        session: AsyncSession, limit: int, offset: int,
        source: str | None, target: str | None,
        status_filter: str | None, keyword: str | None,
    ) -> dict:
        items = await repo.list_dependencies(
            session, limit=limit, offset=offset, source=source, target=target,
            status=status_filter, keyword=keyword,
        )
        total = await repo.count_dependencies(
            session, source=source, target=target,
            status=status_filter, keyword=keyword,
        )
        return {"total": total, "items": [_dep_to_dict(d) for d in items]}

    @staticmethod
    async def get_dependency(session: AsyncSession, dep_id: str) -> dict:
        dep = await repo.get_dependency(session, dep_id)
        if not dep:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "依赖关系不存在")
        return _dep_to_dict(dep)

    @staticmethod
    async def create_dependency(session: AsyncSession, payload: DependencyCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if payload.source_service == payload.target_service:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不允许依赖自身")
        if await repo.get_dependency_by_edge(
            session, payload.source_service, payload.target_service, payload.dependency_type,
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "依赖关系已存在")
        dep = ServiceDependency(
            id=str(uuid.uuid4()),
            source_service=payload.source_service,
            target_service=payload.target_service,
            dependency_type=payload.dependency_type,
            description=payload.description,
            status="active",
        )
        dep = await repo.create_dependency(session, dep)
        await record_audit(session, "dependency.created", "internal",
                           f"edge={payload.source_service}->{payload.target_service} type={payload.dependency_type}",
                           request)
        return _dep_to_dict(dep)

    @staticmethod
    async def update_dependency(
        session: AsyncSession, dep_id: str, payload: DependencyUpdate, request: Request,
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        dep = await repo.get_dependency(session, dep_id)
        if not dep:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "依赖关系不存在")
        if payload.description is not None:
            dep.description = payload.description
        dep = await repo.update_dependency(session, dep)
        await record_audit(session, "dependency.updated", "internal", f"id={dep_id}", request)
        return _dep_to_dict(dep)

    @staticmethod
    async def update_status(
        session: AsyncSession, dep_id: str, new_status: str, request: Request,
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        dep = await repo.get_dependency(session, dep_id)
        if not dep:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "依赖关系不存在")
        dep.status = new_status
        dep = await repo.update_dependency(session, dep)
        await record_audit(session, "dependency.status_changed", "internal",
                           f"id={dep_id} status={new_status}", request)
        return _dep_to_dict(dep)

    @staticmethod
    async def delete_dependency(session: AsyncSession, dep_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        dep = await repo.get_dependency(session, dep_id)
        if not dep:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "依赖关系不存在")
        await repo.delete_dependency(session, dep)
        await record_audit(session, "dependency.deleted", "internal",
                           f"id={dep_id}", request)
        return {"deleted": True, "id": dep_id}
