"""融合平台业务深化测试：健康检查/服务依赖/SLA 合规全生命周期。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}
BAD = {"X-Internal-Token": "wrong"}


# ═══════════════════════════════════════════════════════════
# 服务健康检查记录
# ═══════════════════════════════════════════════════════════

class TestHealthCheck:
    async def test_create_check_success(self, client):
        resp = await client.post("/api/fusion/health-checks", json={
            "service_id": "sm-iam", "status": "healthy", "latency_ms": 12.5,
            "endpoint": "/health", "detail": "探针正常",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["service_id"] == "sm-iam"
        assert data["status"] == "healthy"
        assert data["latency_ms"] == 12.5
        assert "id" in data

    async def test_create_check_requires_token(self, client):
        resp = await client.post("/api/fusion/health-checks", json={
            "service_id": "sm-iam", "status": "healthy",
        })
        assert resp.status_code in (401, 403)

    async def test_create_check_invalid_status_rejected(self, client):
        # Literal 约束由 Pydantic 校验，非法状态返回 422
        resp = await client.post("/api/fusion/health-checks", json={
            "service_id": "sm-iam", "status": "bogus",
        }, headers=H)
        assert resp.status_code == 422

    async def test_list_checks_pagination_and_filter(self, client):
        await client.post("/api/fusion/health-checks", json={
            "service_id": "sm-audit", "status": "unhealthy", "detail": "磁盘满",
        }, headers=H)
        resp = await client.get("/api/fusion/health-checks?status=unhealthy&keyword=磁盘", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(item["status"] == "unhealthy" for item in data["items"])

    async def test_list_checks_service_filter(self, client):
        await client.post("/api/fusion/health-checks", json={
            "service_id": "sm-notify", "status": "degraded",
        }, headers=H)
        resp = await client.get("/api/fusion/health-checks?service_id=sm-notify", headers=H)
        assert resp.status_code == 200
        assert all(item["service_id"] == "sm-notify" for item in resp.json()["items"])

    async def test_get_check_by_id(self, client):
        create = await client.post("/api/fusion/health-checks", json={
            "service_id": "sm-gw", "status": "healthy",
        }, headers=H)
        check_id = create.json()["id"]
        resp = await client.get(f"/api/fusion/health-checks/{check_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == check_id

    async def test_get_check_not_found(self, client):
        resp = await client.get("/api/fusion/health-checks/nonexistent-id", headers=H)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════
# 服务依赖关系
# ═══════════════════════════════════════════════════════════

class TestServiceDependency:
    async def test_create_dependency_success(self, client):
        resp = await client.post("/api/fusion/dependencies", json={
            "source_service": "sm-portal", "target_service": "sm-iam",
            "dependency_type": "sync", "description": "登录校验",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_service"] == "sm-portal"
        assert data["target_service"] == "sm-iam"
        assert data["status"] == "active"

    async def test_create_dependency_duplicate_edge(self, client):
        payload = {
            "source_service": "sm-portal", "target_service": "sm-audit",
            "dependency_type": "async",
        }
        first = await client.post("/api/fusion/dependencies", json=payload, headers=H)
        assert first.status_code == 201
        second = await client.post("/api/fusion/dependencies", json=payload, headers=H)
        assert second.status_code == 409

    async def test_create_dependency_self_loop_rejected(self, client):
        resp = await client.post("/api/fusion/dependencies", json={
            "source_service": "sm-iam", "target_service": "sm-iam",
            "dependency_type": "sync",
        }, headers=H)
        assert resp.status_code == 400

    async def test_create_dependency_requires_token(self, client):
        resp = await client.post("/api/fusion/dependencies", json={
            "source_service": "a", "target_service": "b",
        }, headers=BAD)
        assert resp.status_code in (401, 403)

    async def test_list_dependencies_filter_and_keyword(self, client):
        await client.post("/api/fusion/dependencies", json={
            "source_service": "sm-billing", "target_service": "sm-mq",
            "dependency_type": "async", "description": "计费事件投递",
        }, headers=H)
        resp = await client.get(
            "/api/fusion/dependencies?source=sm-billing&keyword=计费", headers=H,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["source_service"] == "sm-billing"

    async def test_update_dependency_description(self, client):
        create = await client.post("/api/fusion/dependencies", json={
            "source_service": "sm-order", "target_service": "sm-db",
            "dependency_type": "sync",
        }, headers=H)
        dep_id = create.json()["id"]
        resp = await client.patch(f"/api/fusion/dependencies/{dep_id}", json={
            "description": "主库写入",
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["description"] == "主库写入"

    async def test_update_dependency_status_broken(self, client):
        create = await client.post("/api/fusion/dependencies", json={
            "source_service": "sm-cache", "target_service": "sm-redis",
            "dependency_type": "sync",
        }, headers=H)
        dep_id = create.json()["id"]
        resp = await client.patch(f"/api/fusion/dependencies/{dep_id}/status", json={
            "status": "broken",
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "broken"

    async def test_get_dependency_not_found(self, client):
        resp = await client.get("/api/fusion/dependencies/nonexistent", headers=H)
        assert resp.status_code == 404

    async def test_delete_dependency(self, client):
        create = await client.post("/api/fusion/dependencies", json={
            "source_service": "sm-tmp", "target_service": "sm-tgt",
            "dependency_type": "sync",
        }, headers=H)
        dep_id = create.json()["id"]
        resp = await client.delete(f"/api/fusion/dependencies/{dep_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_dependency_not_found(self, client):
        resp = await client.delete("/api/fusion/dependencies/nonexistent", headers=H)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════
# SLA 合规记录
# ═══════════════════════════════════════════════════════════

class TestSLACompliance:
    async def test_create_sla_met(self, client):
        resp = await client.post("/api/fusion/sla", json={
            "service_id": "sm-iam", "period": "2026-09",
            "availability_pct": 99.99, "incident_count": 0,
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "met"
        assert data["period"] == "2026-09"

    async def test_create_sla_breached_derived(self, client):
        resp = await client.post("/api/fusion/sla", json={
            "service_id": "sm-flaky", "period": "2026-09",
            "availability_pct": 95.0, "incident_count": 3,
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["status"] == "breached"

    async def test_create_sla_duplicate_period(self, client):
        payload = {
            "service_id": "sm-dup", "period": "2026-08",
            "availability_pct": 99.9,
        }
        first = await client.post("/api/fusion/sla", json=payload, headers=H)
        assert first.status_code == 201
        second = await client.post("/api/fusion/sla", json=payload, headers=H)
        assert second.status_code == 409

    async def test_create_sla_invalid_period(self, client):
        resp = await client.post("/api/fusion/sla", json={
            "service_id": "sm-iam", "period": "2026/09",
            "availability_pct": 99.9,
        }, headers=H)
        assert resp.status_code == 422

    async def test_create_sla_out_of_range(self, client):
        resp = await client.post("/api/fusion/sla", json={
            "service_id": "sm-iam", "period": "2026-09",
            "availability_pct": 150.0,
        }, headers=H)
        assert resp.status_code == 422

    async def test_create_sla_requires_token(self, client):
        resp = await client.post("/api/fusion/sla", json={
            "service_id": "sm-iam", "period": "2026-09",
            "availability_pct": 99.9,
        })
        assert resp.status_code in (401, 403)

    async def test_list_sla_filter_and_keyword(self, client):
        await client.post("/api/fusion/sla", json={
            "service_id": "sm-sla-search", "period": "2026-07",
            "availability_pct": 80.0, "note": "数据库故障",
        }, headers=H)
        resp = await client.get(
            "/api/fusion/sla?status=breached&keyword=数据库", headers=H,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["status"] == "breached"

    async def test_update_sla_recompute_status(self, client):
        create = await client.post("/api/fusion/sla", json={
            "service_id": "sm-repair", "period": "2026-06",
            "availability_pct": 99.95,
        }, headers=H)
        record_id = create.json()["id"]
        # 下调可用性，状态应自动翻转为 breached
        resp = await client.patch(f"/api/fusion/sla/{record_id}", json={
            "availability_pct": 90.0,
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "breached"
        assert resp.json()["availability_pct"] == 90.0

    async def test_get_sla_by_id(self, client):
        create = await client.post("/api/fusion/sla", json={
            "service_id": "sm-get", "period": "2026-05",
            "availability_pct": 99.9,
        }, headers=H)
        record_id = create.json()["id"]
        resp = await client.get(f"/api/fusion/sla/{record_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == record_id

    async def test_get_sla_not_found(self, client):
        resp = await client.get("/api/fusion/sla/nonexistent", headers=H)
        assert resp.status_code == 404

    async def test_delete_sla(self, client):
        create = await client.post("/api/fusion/sla", json={
            "service_id": "sm-del", "period": "2026-04",
            "availability_pct": 99.9,
        }, headers=H)
        record_id = create.json()["id"]
        resp = await client.delete(f"/api/fusion/sla/{record_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
