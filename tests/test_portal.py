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
        assert response.json()["service"] == "sm-fusion-platform"
        assert response.json()["checks"]["catalog"] == "ok"


def test_overview_returns_enterprise_service_metrics():
    with TestClient(app) as client:
        response = client.get("/api/overview")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 28
        assert len(payload["services"]) == 28
        assert all("latency_ms" in service for service in payload["services"])
        assert payload["platform"]["name"] == "SM Fusion Platform"
        assert payload["business_status"] in {"operational", "degraded", "critical"}
        assert all("owner" in service and "slo" in service for service in payload["services"])


def test_version_endpoint_is_stable():
    with TestClient(app) as client:
        response = client.get("/api/version")
        assert response.status_code == 200
        assert response.json()["version"] == "4.2.0"


def test_service_catalog_and_semantic_versions_are_valid():
    services = load_services()
    assert len({service["id"] for service in services}) == len(services)
    assert version_tuple("1.2.0") > version_tuple("1.1.0")


def test_governance_exposes_enterprise_ownership():
    with TestClient(app) as client:
        payload = client.get("/api/governance").json()
        assert "平台工程部" in payload["owners"]
        assert payload["tiers"]["P1"] >= 7
        assert "ISO27001" in payload["compliance"]
        assert "SM IAM" in {service["name"] for service in payload["services"]}
        assert "SM AgentOps" in {service["name"] for service in payload["services"]}

def test_ops_metrics_endpoint_reports_runtime_counts():
    with TestClient(app) as client:
        client.get("/health")
        response = client.get("/api/ops/metrics")
        assert response.status_code == 200
        payload = response.json()
        assert payload["service"] == "sm-fusion-platform"
        assert payload["requests_total"] >= 1




def test_crypto_status():
    with TestClient(app) as client:
        response = client.get('/api/crypto/status')
        assert response.status_code == 200
        assert response.json()['algorithm'] == 'SM3/SM4'



def test_prometheus_metrics():
    with TestClient(app) as client:
        response = client.get('/metrics')
        assert response.status_code == 200
        assert 'sm_fusion_requests_total' in response.text



def test_integration_check_contract():
    with TestClient(app) as client:
        payload = client.get('/api/integration/check').json()
        assert payload['total'] == 28
        assert payload['status'] in {'ok', 'degraded'}
        assert isinstance(payload['unavailable'], list)



def test_gateway_and_audit_contracts():
    with TestClient(app) as client:
        routes = client.get('/api/gateway/routes').json()
        assert routes['count'] == 28
        assert all('upstream' in item for item in routes['routes'])
        audit = client.get('/api/audit/contract').json()
        assert audit['integrity'] == 'SM3'
        assert 'request_id' in audit['required']



def test_oidc_and_event_contracts():
    with TestClient(app) as client:
        oidc = client.get('/api/oidc/config').json()
        assert oidc['pkce'] == 'S256'
        assert 'openid' in oidc['scopes']
        events = client.get('/api/events/contract').json()
        assert events['delivery'] == 'at-least-once'
        assert events['deduplication_key'] == 'event_id'


