import pytest

from rkjo_kernel.mission import Mission, MissionStatus


def test_mission_normalizes_domain_and_generates_identifier():
    mission = Mission(
        objective="Teach fractions",
        domain=" Education ",
    )

    assert mission.domain == "education"
    assert mission.mission_id
    assert mission.status == MissionStatus.PENDING
    assert mission.is_terminal is False


def test_mission_rejects_empty_objective():
    with pytest.raises(ValueError, match="objective"):
        Mission(objective="   ", domain="education")


def test_mission_attaches_workflow_once():
    mission = Mission(objective="Teach fractions", domain="education")

    mission.attach_workflow("workflow-1")
    mission.attach_workflow("workflow-1")
    mission.attach_workflow("workflow-2")

    assert mission.workflow_execution_ids == ["workflow-1", "workflow-2"]


def test_mission_success_lifecycle():
    mission = Mission(objective="Teach fractions", domain="education")

    mission.start()
    assert mission.status == MissionStatus.RUNNING
    assert mission.started_at is not None

    result = {"mastery": 0.9}
    mission.complete(result=result)

    assert mission.status == MissionStatus.COMPLETED
    assert mission.result == result
    assert mission.completed_at is not None
    assert mission.is_terminal is True


def test_mission_failure_requires_error_message():
    mission = Mission(objective="Teach fractions", domain="education")
    mission.start()

    with pytest.raises(ValueError, match="error message"):
        mission.fail("  ")


def test_mission_rejects_invalid_transition():
    mission = Mission(objective="Teach fractions", domain="education")

    with pytest.raises(ValueError, match="Cannot move mission"):
        mission.complete()
