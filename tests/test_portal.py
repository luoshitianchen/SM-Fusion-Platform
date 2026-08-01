from fastapi.testclient import TestClient
from app.main import app


def test_portal_and_health():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        response = client.get("/health", headers={"X-Request-Id": "fusion-test"})
        assert response.status_code == 200
        assert response.headers["X-Request-Id"] == "fusion-test"
        assert response.headers["X-Frame-Options"] == "DENY"
