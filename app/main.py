from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse

SERVICES = {
    "erp": {
        "name": "SM ERP",
        "internal_url": os.getenv("ERP_INTERNAL_URL", "http://sm-erp:8100"),
        "public_url": os.getenv("ERP_PUBLIC_URL", "http://127.0.0.1:8100"),
        "description": "企业身份、组织、角色与审计中心",
    },
    "knowledge": {
        "name": "SM Knowledge Bot",
        "internal_url": os.getenv("KB_INTERNAL_URL", "http://knowledge-bot:8000"),
        "public_url": os.getenv("KB_PUBLIC_URL", "http://127.0.0.1:8010"),
        "description": "RAG、多轮对话、Agent 与权限知识检索",
    },
}

app = FastAPI(title="SM Fusion Platform", version="1.0.0", docs_url=None, redoc_url=None)
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


async def probe(key: str, config: dict[str, str]) -> dict[str, str]:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3, connect=2)) as client:
            response = await client.get(f"{config['internal_url']}/health")
            response.raise_for_status()
        state = "healthy"
    except (httpx.HTTPError, ValueError):
        state = "unavailable"
    return {"id": key, "name": config["name"], "description": config["description"], "url": config["public_url"], "status": state, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


@app.get("/", include_in_schema=False)
def portal() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/readyz")
async def ready() -> dict[str, object]:
    services = await asyncio.gather(*(probe(key, value) for key, value in SERVICES.items()))
    return {"status": "ready" if all(item["status"] == "healthy" for item in services) else "degraded", "services": services}


@app.get("/api/services")
async def service_catalog() -> dict[str, object]:
    services = await asyncio.gather(*(probe(key, value) for key, value in SERVICES.items()))
    return {"items": services, "healthy": sum(item["status"] == "healthy" for item in services), "total": len(services)}


@app.get("/api/overview")
async def overview() -> dict[str, object]:
    services = await asyncio.gather(*(probe(key, value) for key, value in SERVICES.items()))
    return {"platform": {"name": app.title, "version": app.version}, "services": services, "healthy": sum(item["status"] == "healthy" for item in services), "total": len(services), "refreshed_at": time.time()}
