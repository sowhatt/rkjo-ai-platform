from pathlib import Path


def test_compose_declares_production_services():
    content = Path(
        "docker-compose.yml"
    ).read_text(
        encoding="utf-8"
    )

    for service in (
        "rabbitmq:",
        "postgres:",
        "api:",
        "worker:",
    ):
        assert service in content


def test_api_has_healthcheck():
    content = Path(
        "docker-compose.yml"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "http://localhost:8000/health"
        in content
    )


def test_no_localhost_database_inside_compose():
    content = Path(
        "docker-compose.yml"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "@localhost:5432"
        not in content
    )


def test_worker_has_liveness_healthcheck():
    content = Path(
        "docker-compose.yml"
    ).read_text(
        encoding="utf-8"
    )

    assert "RKJO_WORKER_HEALTH_PORT" in content
    assert "http://localhost:8081/live" in content
