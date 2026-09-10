"""融合门户业务路由：版本、治理、集成检查、网关路由、审计/OIDC/事件契约。"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import settings
from app.services.portal import (
    PORTAL_VERSION,
    governance_data,
    integration_check_data,
    load_services,
)

router = APIRouter(tags=["portal"])


@router.get("/api/version")
async def version() -> dict[str, str]:
    return {"name": settings.DISPLAY_NAME, "version": PORTAL_VERSION, "channel": "stable"}


@router.get("/api/governance")
async def governance(request: Request) -> dict[str, object]:
    return await governance_data(request)


@router.get("/api/integration/check")
async def integration_check(request: Request) -> dict[str, object]:
    return await integration_check_data(request)


@router.get("/api/gateway/routes")
async def gateway_routes() -> dict[str, object]:
    services = load_services()
    return {
        "routes": [
            {
                "id": item["id"], "upstream": item["internal_url"],
                "health": item.get("health_path", "/health"), "public": item["public_url"],
                "auth": "iam" if item["id"] not in {"fusion", "health"} else "portal",
            }
            for item in services
        ],
        "count": len(services),
    }


@router.get("/api/audit/contract")
async def audit_contract() -> dict[str, object]:
    return {
        "event_schema": "v1",
        "required": ["event_id", "service", "action", "actor", "timestamp", "request_id"],
        "transport": "event-bus", "integrity": "SM3", "retention_days": 365,
    }


@router.get("/api/oidc/config")
async def oidc_config() -> dict[str, object]:
    return {
        "issuer": "https://iam.example.invalid",
        "authorization_endpoint": "https://iam.example.invalid/authorize",
        "token_endpoint": "https://iam.example.invalid/token",
        "jwks_uri": "https://iam.example.invalid/.well-known/jwks.json",
        "scopes": ["openid", "profile", "email", "roles"], "pkce": "S256",
    }


@router.get("/api/events/contract")
async def event_contract() -> dict[str, object]:
    return {
        "version": "1.0", "transport": "event-bus", "delivery": "at-least-once",
        "deduplication_key": "event_id",
        "retry": {"max_attempts": 5, "backoff_seconds": [1, 5, 30, 120, 600]},
        "dead_letter": "sm-audit-log-center",
    }
