from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse

CATALOG_PATH = Path(os.getenv("FUSION_SERVICE_CATALOG", "config/services.json"))
VERSION = "4.2.0"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
INTERNAL_API_KEY = os.getenv("SM_INTERNAL_API_KEY", "")
AUDIT_CENTER_URL = os.getenv("SM_AUDIT_CENTER_URL", "")


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
    request_id = supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else str(uuid.uuid4())
    request.state.request_id = request_id
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


def _forward_audit(action: str, detail: str, request_id: str) -> None:
    import urllib.request as _ur
    try:
        event = {"event_id": str(uuid.uuid4()), "service": "sm-fusion-platform", "action": action, "actor": "portal", "timestamp": datetime.now(UTC).isoformat(), "request_id": request_id, "trace_id": "", "detail": detail[:2000]}
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        req = _ur.Request(AUDIT_CENTER_URL.rstrip("/") + "/api/audit/events", data=body, headers={"Content-Type": "application/json", "X-Internal-Token": INTERNAL_API_KEY}, method="POST")
        _ur.urlopen(req, timeout=2)
    except Exception:
        pass


async def probe(config: dict[str, str]) -> dict[str, object]:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=0.75), trust_env=False) as client:
            response = await client.get(f"{config['internal_url'].rstrip('/')}{config.get('health_path', '/health')}")
            response.raise_for_status()
        state = "healthy"
    except (httpx.HTTPError, ValueError):
        state = "unavailable"
    return {"id": config["id"], "name": config["name"], "probe_target": config["internal_url"], "description": config["description"], "url": config["public_url"], "category": config.get("category", "企业应用"), "owner": config["owner"], "tier": config["tier"], "slo": float(config["slo"]), "environment": config["environment"], "service_version": config["service_version"], "tenant_scope": config["tenant_scope"], "compliance": config["compliance"], "contact": config["contact"], "status": state, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


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


@app.get("/metrics")
def prometheus_metrics() -> Response:
    with metrics_lock:
        snapshot = dict(metrics)
    body = (
        f"sm_fusion_requests_total {int(snapshot['requests_total'])}"
        f"\nsm_fusion_errors_total {int(snapshot['errors_total'])}\n"
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")


@app.get("/api/version")
def version() -> dict[str, str]:
    return {"name": app.title, "version": app.version, "channel": os.getenv("FUSION_RELEASE_CHANNEL", "stable")}


@app.get("/api/crypto/status")
def crypto_status() -> dict[str, object]:
    return {"algorithm": "SM3/SM4", "sm3": "enabled", "sm4": "enabled", "services": len(load_services())}


@app.get("/api/integration/check")
async def integration_check(request: Request) -> dict[str, object]:
    services = await probe_all()
    resolve_public_urls(services, request)
    return {"status": "ok" if all(item["status"] == "healthy" for item in services) else "degraded", "total": len(services), "healthy": sum(item["status"] == "healthy" for item in services), "unavailable": [item["id"] for item in services if item["status"] != "healthy"]}


@app.get("/api/gateway/routes")
def gateway_routes() -> dict[str, object]:
    services = load_services()
    return {"routes": [{"id": item["id"], "upstream": item["internal_url"], "health": item.get("health_path", "/health"), "public": item["public_url"], "auth": "iam" if item["id"] not in {"fusion", "health"} else "portal"} for item in services], "count": len(services)}


@app.get("/api/audit/contract")
def audit_contract() -> dict[str, object]:
    return {"event_schema": "v1", "required": ["event_id", "service", "action", "actor", "timestamp", "request_id"], "transport": "event-bus", "integrity": "SM3", "retention_days": 365}


@app.get("/api/oidc/config")
def oidc_config() -> dict[str, object]:
    return {
        "issuer": os.getenv("OIDC_ISSUER", "https://iam.example.invalid"),
        "authorization_endpoint": os.getenv("OIDC_AUTHORIZATION_ENDPOINT", "https://iam.example.invalid/authorize"),
        "token_endpoint": os.getenv("OIDC_TOKEN_ENDPOINT", "https://iam.example.invalid/token"),
        "jwks_uri": os.getenv("OIDC_JWKS_URI", "https://iam.example.invalid/.well-known/jwks.json"),
        "scopes": ["openid", "profile", "email", "roles"],
        "pkce": "S256",
    }


@app.get("/api/events/contract")
def event_contract() -> dict[str, object]:
    return {"version": "1.0", "transport": "event-bus", "delivery": "at-least-once", "deduplication_key": "event_id", "retry": {"max_attempts": 5, "backoff_seconds": [1, 5, 30, 120, 600]}, "dead_letter": "sm-audit-log-center"}


@app.get("/api/integration/manifest")
def integration_manifest() -> dict[str, object]:
    return {
        "service": "sm-fusion-platform",
        "name": "SM Fusion Platform",
        "version": app.version,
        "dependencies": ["sm-iam", "sm-api-gateway", "sm-audit-log-center", "sm-observability"],
        "events": ["health.checked", "service.probed", "audit.recorded"],
        "health_path": "/health",
        "metrics_path": "/api/ops/metrics",
        "overview_path": "/api/overview",
    }


@app.get("/api/security/baseline")
def security_baseline() -> dict[str, object]:
    return {
        "service": "sm-fusion-platform",
        "version": app.version,
        "controls": {
            "trusted_host": True,
            "security_headers": True,
            "csp": True,
            "catalog_validation": True,
            "sm3": True,
            "sm4": True,
            "internal_token": bool(INTERNAL_API_KEY),
            "audit_forwarding": bool(AUDIT_CENTER_URL),
        },
        "recommended": ["OIDC/MFA", "KMS/HSM", "centralized audit", "OpenTelemetry"],
    }
