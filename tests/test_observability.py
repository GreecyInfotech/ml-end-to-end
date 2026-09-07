from fastapi.testclient import TestClient


def test_gateway_prometheus_and_sre_endpoints_expose_request_state():
    from gateway.main import app

    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "obs-test-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "obs-test-123"

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "vessel_http_requests_total" in metrics.text
    assert "vessel_slo_availability_target" in metrics.text
    assert "vessel_process_cpu_percent" in metrics.text
    assert "vessel_process_memory_bytes" in metrics.text
    assert "vessel_service_throughput_requests_per_second" in metrics.text

    sre = client.get("/sre")
    assert sre.status_code == 200
    assert sre.json()["service"] == "vessel-delay-gateway"
    assert 0 <= sre.json()["error_budget_remaining_ratio"] <= 1


def test_api_prometheus_endpoint_is_scrape_compatible():
    from api.main import app

    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "vessel_http_request_duration_seconds" in response.text
    assert "vessel_service_availability_ratio" in response.text
