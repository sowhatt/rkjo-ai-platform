from pathlib import Path


def test_compose_runs_workflow_schema_bootstrap_before_services():
    content = Path("docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow-migrate:" in content
    assert (
        "rkjo_kernel.workflow.schema_bootstrap"
        in content
    )
    assert content.count(
        "condition: service_completed_successfully"
    ) >= 2


def test_workflow_bootstrap_module_is_packaged_in_platform_image():
    dockerfile = Path("Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "COPY platform ./platform" in dockerfile
    assert "PYTHONPATH=/app/platform/kernel" in dockerfile
