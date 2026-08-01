from fastapi.testclient import TestClient
from app.main import app


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
