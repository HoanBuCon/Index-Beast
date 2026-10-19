import time


def test_health_ok_when_all_services_up(client):
    res = client.get("/api/v1/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok", "checks": {"postgres": True, "redis": True, "qdrant": True}}


def test_health_503_when_a_service_fails(client, fakes):
    fakes["redis"].fail = True

    res = client.get("/api/v1/health")

    assert res.status_code == 503
    assert res.json()["status"] == "degraded"
    assert res.json()["checks"] == {"postgres": True, "redis": False, "qdrant": True}


def test_health_does_not_hang_on_slow_service(client, fakes):
    fakes["qdrant"].hang = True

    start = time.perf_counter()
    res = client.get("/api/v1/health")

    assert res.status_code == 503
    assert res.json()["checks"]["qdrant"] is False
    assert time.perf_counter() - start < 2  # timeout 0.2 s trong settings test, không chờ 10 s


def test_request_id_is_echoed_or_generated(client):
    assert client.get("/api/v1/health", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"] == "abc123"
    assert len(client.get("/api/v1/health").headers["X-Request-ID"]) == 16


def test_openapi_is_served(client):
    paths = client.get("/api/openapi.json").json()["paths"]
    assert "/api/v1/health" in paths
