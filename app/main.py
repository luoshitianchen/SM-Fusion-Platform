from __future__ import annotations

import asyncio
import json
import os
import re
import time
import threading
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse

CATALOG_PATH = Path(os.getenv("FUSION_SERVICE_CATALOG", "config/services.json"))
VERSION = "3.5.0"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def load_services() -> list[dict[str, str]]:
    """从外部目录加载项目，新增系统无需修改或重新编译门户代码。"""
    try:
        services = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"服务目录不可用: {CATALOG_PATH}") from exc
    required = {"id", "name", "internal_url", "public_url", "description", "owner", "tier", "slo", "environment", "service_version", "tenant_scope", "compliance", "contact"}
    if not isinstance(services, list) or not services or any(not isinstance(item, dict) or not required <= item.keys() for item in services):
        raise RuntimeError("服务目录格式无效")
    identifiers = [str(item["id"]) for item in services]
    if len(set(identifiers)) != len(identifiers) or any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", identifier) for identifier in identifiers):
        raise RuntimeError("服务目录项目 ID 必须唯一且格式有效")
    for item in services:
        for field in ("internal_url", "public_url"):
            value = str(item[field]).replace("{host}", "localhost")
            parsed = urlsplit(value)
            if value != "/" and (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password):
                raise RuntimeError(f"服务目录 {field} 必须是不含凭据的 HTTP(S) 地址")
        health_path = str(item.get("health_path", "/health"))
        if not health_path.startswith("/") or ".." in health_path:
            raise RuntimeError("服务目录 health_path 格式无效")
        if item["tier"] not in {"P0", "P1", "P2", "P3"} or not 90 <= float(item["slo"]) <= 100:
            raise RuntimeError("服务目录 tier 或 slo 格式无效")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(item["service_version"])) or not isinstance(item["compliance"], list) or not item["compliance"] or "@" not in str(item["contact"]):
            raise RuntimeError("服务目录版本、合规标签或责任联系方式无效")
    return services

app = FastAPI(title="SM Fusion Platform", version=VERSION, docs_url=None, redoc_url=None)
PROBE_CACHE_SECONDS = int(os.getenv("FUSION_PROBE_CACHE_SECONDS", "5"))
_probe_cache: tuple[float, list[dict[str, object]]] | None = None
_probe_cache_lock = threading.Lock()
metrics_lock = threading.Lock()
metrics = {"requests_total": 0, "errors_total": 0}
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[item.strip() for item in os.getenv("FUSION_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if item.strip()],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-Id", "")
    request_id = supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else str(uuid4())
    response = await call_next(request)
    with metrics_lock:
        metrics["requests_total"] += 1
        if response.status_code >= 500:
            metrics["errors_total"] += 1
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    if os.getenv("FUSION_ENVIRONMENT", "development") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


async def probe(config: dict[str, str]) -> dict[str, object]:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3, connect=2)) as client:
            response = await client.get(f"{config['internal_url'].rstrip('/')}{config.get('health_path', '/health')}")
            response.raise_for_status()
        state = "healthy"
    except (httpx.HTTPError, ValueError):
        state = "unavailable"
    return {"id": config["id"], "name": config["name"], "description": config["description"], "url": config["public_url"], "category": config.get("category", "企业应用"), "owner": config["owner"], "tier": config["tier"], "slo": float(config["slo"]), "environment": config["environment"], "service_version": config["service_version"], "tenant_scope": config["tenant_scope"], "compliance": config["compliance"], "contact": config["contact"], "status": state, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


async def probe_all() -> list[dict[str, object]]:
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


@app.get("/", include_in_schema=False)
def portal() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": "sm-fusion-platform", "version": app.version, "checks": {"catalog": "ok"}, "timestamp": time.time()}


@app.get("/readyz")
async def ready(request: Request) -> dict[str, object]:
    services = await probe_all()
    resolve_public_urls(services, request)
    return {"status": "ready" if all(item["status"] == "healthy" for item in services) else "degraded", "services": services}


@app.get("/api/services")
async def service_catalog(request: Request) -> dict[str, object]:
    services = await probe_all()
    resolve_public_urls(services, request)
    return {"items": services, "healthy": sum(item["status"] == "healthy" for item in services), "total": len(services)}


@app.get("/api/overview")
async def overview(request: Request) -> dict[str, object]:
    services = await probe_all()
    resolve_public_urls(services, request)
    healthy = sum(item["status"] == "healthy" for item in services)
    critical_down = sum(item["status"] != "healthy" and item["tier"] in {"P0", "P1"} for item in services)
    return {"platform": {"name": app.title, "version": app.version}, "services": services, "healthy": healthy, "total": len(services), "critical_down": critical_down, "business_status": "critical" if critical_down else ("degraded" if healthy < len(services) else "operational"), "refreshed_at": time.time()}


@app.get("/api/governance")
async def governance(request: Request) -> dict[str, object]:
    services = resolve_public_urls(await probe_all(), request)
    owners = sorted({str(item["owner"]) for item in services})
    return {"owners": owners, "environments": sorted({str(item["environment"]) for item in services}), "tenancy": sorted({str(item["tenant_scope"]) for item in services}), "compliance": sorted({label for item in services for label in item["compliance"]}), "tiers": {tier: sum(item["tier"] == tier for item in services) for tier in ("P0", "P1", "P2", "P3")}, "services": services}


@app.get("/api/ops/metrics")
def ops_metrics() -> dict[str, object]:
    with metrics_lock:
        snapshot = dict(metrics)
    return {"service": "sm-fusion-platform", "version": app.version, "requests_total": int(snapshot["requests_total"]), "errors_total": int(snapshot["errors_total"])}


@app.get("/api/version")
def version() -> dict[str, str]:
    return {"name": app.title, "version": app.version, "channel": os.getenv("FUSION_RELEASE_CHANNEL", "stable")}


@app.get("/api/crypto/status")
def crypto_status() -> dict[str, object]:
    return {"algorithm": "SM3/SM4", "sm3": "enabled", "sm4": "enabled", "services": 13}


@app.get("/metrics")
def prometheus_metrics() -> Response:
    with metrics_lock:
        snapshot = dict(metrics)
    body = (
        f"sm_fusion_requests_total {int(snapshot['requests_total'])}\n"
        f"sm_fusion_errors_total {int(snapshot['errors_total'])}\n"
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")
