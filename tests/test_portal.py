from fastapi.testclient import TestClient
from app.main import app, load_services
from desktop.main import version_tuple


def test_portal_and_health():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        response = client.get("/health", headers={"X-Request-Id": "fusion-test"})
        assert response.status_code == 200
        assert response.headers["X-Request-Id"] == "fusion-test"
        assert response.headers["X-Frame-Options"] == "DENY"


def test_overview_returns_enterprise_service_metrics():
    with TestClient(app) as client:
        response = client.get("/api/overview")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 3
        assert len(payload["services"]) == 3
        assert all("latency_ms" in service for service in payload["services"])
        assert payload["platform"]["name"] == "SM Fusion Platform"
        assert payload["business_status"] in {"operational", "degraded", "critical"}
        assert all("owner" in service and "slo" in service for service in payload["services"])


def test_version_endpoint_is_stable():
    with TestClient(app) as client:
        response = client.get("/api/version")
        assert response.status_code == 200
        assert response.json()["version"] == "1.2.0"


def test_service_catalog_and_semantic_versions_are_valid():
    services = load_services()
    assert len({service["id"] for service in services}) == len(services)
    assert version_tuple("1.2.0") > version_tuple("1.1.0")


def test_governance_exposes_enterprise_ownership():
    with TestClient(app) as client:
        payload = client.get("/api/governance").json()
        assert "平台工程部" in payload["owners"]
        assert payload["tiers"]["P1"] == 2
