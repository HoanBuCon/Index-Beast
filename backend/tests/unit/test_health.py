import time


def test_health_ok_when_all_resources_up(client):
    res = client.get("/api/v1/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok", "checks": {"postgres": True, "redis": True, "qdrant": True}}


def test_health_503_when_a_resource_fails(client, fakes):
    fakes["redis"].fail = True

    res = client.get("/api/v1/health")

    assert res.status_code == 503
    assert res.json() == {"status": "degraded", "checks": {"postgres": True, "redis": False, "qdrant": True}}


def test_health_does_not_hang_on_slow_resource(client, fakes):
    fakes["qdrant"].hang = True

    start = time.perf_counter()
    res = client.get("/api/v1/health")

    assert res.status_code == 503
    assert res.json()["checks"]["qdrant"] is False
    assert time.perf_counter() - start < 2  # timeout 0.2 s trong settings test, không chờ đủ 10 s
