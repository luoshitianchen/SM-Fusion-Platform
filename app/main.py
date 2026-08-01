from __future__ import annotations

import asyncio
import json
import os
import time
import threading
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse

CATALOG_PATH = Path(os.getenv("FUSION_SERVICE_CATALOG", "config/services.json"))


def load_services() -> list[dict[str, str]]:
    """从外部目录加载项目，新增系统无需修改或重新编译门户代码。"""
    try:
        services = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"服务目录不可用: {CATALOG_PATH}") from exc
    required = {"id", "name", "internal_url", "public_url", "description"}
    if not isinstance(services, list) or not services or any(not isinstance(item, dict) or not required <= item.keys() for item in services):
        raise RuntimeError("服务目录格式无效")
    return services

app = FastAPI(title="SM Fusion Platform", version="1.0.0", docs_url=None, redoc_url=None)
PROBE_CACHE_SECONDS = int(os.getenv("FUSION_PROBE_CACHE_SECONDS", "5"))
_probe_cache: tuple[float, list[dict[str, object]]] | None = None
_probe_cache_lock = threading.Lock()
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[item.strip() for item in os.getenv("FUSION_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if item.strip()],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id[:64]
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
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
    return {"id": config["id"], "name": config["name"], "description": config["description"], "url": config["public_url"], "category": config.get("category", "企业应用"), "status": state, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


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
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


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
    return {"platform": {"name": app.title, "version": app.version}, "services": services, "healthy": sum(item["status"] == "healthy" for item in services), "total": len(services), "refreshed_at": time.time()}


@app.get("/api/version")
def version() -> dict[str, str]:
    return {"name": app.title, "version": app.version, "channel": os.getenv("FUSION_RELEASE_CHANNEL", "stable")}
