"""融合门户服务：服务目录加载、健康探针、治理与网关聚合。

核心业务逻辑自 app/main.py.bak (v4.2.0) 整合至新架构。
服务目录字段校验：id/name/internal_url/public_url/description/owner/tier/slo/
environment/service_version/tenant_scope/compliance/contact。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import Request

CATALOG_PATH = Path(os.getenv("FUSION_SERVICE_CATALOG", "config/services.json"))
# 门户对外契约版本（稳定版），与运行时构建版本解耦
PORTAL_VERSION = "4.1.0"
PROBE_CACHE_SECONDS = int(os.getenv("FUSION_PROBE_CACHE_SECONDS", "5"))

_probe_cache: tuple[float, list[dict[str, object]]] | None = None
_probe_cache_lock = threading.Lock()

_REQUIRED_FIELDS = {
    "id", "name", "internal_url", "public_url", "description", "owner", "tier",
    "slo", "environment", "service_version", "tenant_scope", "compliance", "contact",
}


def load_services() -> list[dict[str, str]]:
    """从外部目录加载服务，新增系统无需修改门户代码。"""
    try:
        services = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"服务目录不可用: {CATALOG_PATH}") from exc
    if not isinstance(services, list) or not services or any(
        not isinstance(item, dict) or not item.keys() >= _REQUIRED_FIELDS for item in services
    ):
        raise RuntimeError("服务目录格式无效")
    identifiers = [str(item["id"]) for item in services]
    if len(set(identifiers)) != len(identifiers) or any(
        not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", identifier) for identifier in identifiers
    ):
        raise RuntimeError("服务目录项目 ID 必须唯一且格式有效")
    for item in services:
        for field in ("internal_url", "public_url"):
            value = str(item[field]).replace("{host}", "localhost")
            parsed = urlsplit(value)
            if value != "/" and (
                parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password
            ):
                raise RuntimeError(f"服务目录 {field} 必须是不含凭据的 HTTP(S) 地址")
        health_path = str(item.get("health_path", "/health"))
        if not health_path.startswith("/") or ".." in health_path:
            raise RuntimeError("服务目录 health_path 格式无效")
        if item["tier"] not in {"P0", "P1", "P2", "P3"} or not 90 <= float(item["slo"]) <= 100:
            raise RuntimeError("服务目录 tier 或 slo 格式无效")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(item["service_version"])) or not isinstance(
            item["compliance"], list
        ) or not item["compliance"] or "@" not in str(item["contact"]):
            raise RuntimeError("服务目录版本、合规标签或责任联系方式无效")
    return services


async def probe(config: dict[str, str]) -> dict[str, object]:
    """探测单个服务健康状态，失败时快速降级为 unavailable。"""
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=0.75), trust_env=False) as client:
            response = await client.get(
                f"{config['internal_url'].rstrip('/')}{config.get('health_path', '/health')}"
            )
            response.raise_for_status()
        state = "healthy"
    except (httpx.HTTPError, ValueError):
        state = "unavailable"
    return {
        "id": config["id"], "name": config["name"], "probe_target": config["internal_url"],
        "description": config["description"], "url": config["public_url"],
        "category": config.get("category", "企业应用"), "owner": config["owner"],
        "tier": config["tier"], "slo": float(config["slo"]), "environment": config["environment"],
        "service_version": config["service_version"], "tenant_scope": config["tenant_scope"],
        "compliance": config["compliance"], "contact": config["contact"], "status": state,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


async def probe_all() -> list[dict[str, object]]:
    """并发探测全部服务，带短时间缓存。"""
    global _probe_cache
    now = time.monotonic()
    with _probe_cache_lock:
        if _probe_cache and now - _probe_cache[0] < PROBE_CACHE_SECONDS:
            return [dict(item) for item in _probe_cache[1]]
    services = await asyncio.gather(*(probe(service) for service in load_services()))
    with _probe_cache_lock:
        _probe_cache = (time.monotonic(), services)
    return [dict(item) for item in services]


def resolve_public_urls(services: list[dict[str, object]], request: Request) -> list[dict[str, object]]:
    host = urlsplit(str(request.base_url)).hostname or "127.0.0.1"
    for service in services:
        service["url"] = str(service["url"]).replace("{host}", host)
    return services


async def overview_data(request: Request) -> dict[str, object]:
    services = await probe_all()
    resolve_public_urls(services, request)
    healthy = sum(item["status"] == "healthy" for item in services)
    critical_down = sum(item["status"] != "healthy" and item["tier"] in {"P0", "P1"} for item in services)
    business_status = (
        "critical" if critical_down else ("degraded" if healthy < len(services) else "operational")
    )
    return {
        "platform": {"name": "SM Fusion Platform", "version": PORTAL_VERSION},
        "services": services, "healthy": healthy, "total": len(services),
        "critical_down": critical_down, "business_status": business_status,
        "refreshed_at": time.time(),
    }


async def governance_data(request: Request) -> dict[str, object]:
    services = resolve_public_urls(await probe_all(), request)
    return {
        "owners": sorted({str(item["owner"]) for item in services}),
        "environments": sorted({str(item["environment"]) for item in services}),
        "tenancy": sorted({str(item["tenant_scope"]) for item in services}),
        "compliance": sorted({label for item in services for label in item["compliance"]}),
        "tiers": {tier: sum(item["tier"] == tier for item in services) for tier in ("P0", "P1", "P2", "P3")},
        "services": services,
    }


async def integration_check_data(request: Request) -> dict[str, object]:
    services = await probe_all()
    resolve_public_urls(services, request)
    return {
        "status": "ok" if all(item["status"] == "healthy" for item in services) else "degraded",
        "total": len(services),
        "healthy": sum(item["status"] == "healthy" for item in services),
        "unavailable": [item["id"] for item in services if item["status"] != "healthy"],
    }
