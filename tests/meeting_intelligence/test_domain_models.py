from datetime import datetime, timezone

import pytest

from rkjo_meeting_intelligence.domain.models import (
    ActionItem,
    ActionStatus,
    Decision,
    DecisionStatus,
    Meeting,
    MeetingStatus,
    Participant,
    TranscriptSegment,
)


def test_meeting_normalizes_required_fields():
    meeting = Meeting(
        meeting_id=" meeting-1 ",
        tenant_id=" tenant-1 ",
        title=" Comité de direction ",
        created_by=" user-1 ",
    )

    assert meeting.meeting_id == "meeting-1"
    assert meeting.tenant_id == "tenant-1"
    assert meeting.title == "Comité de direction"
    assert meeting.created_by == "user-1"
    assert meeting.status == MeetingStatus.DRAFT


def test_meeting_rejects_empty_title():
    with pytest.raises(
        ValueError,
        match="title must not be empty",
    ):
        Meeting(
            meeting_id="meeting-1",
            tenant_id="tenant-1",
            title="   ",
            created_by="user-1",
        )


def test_meeting_rejects_end_before_start():
    start = datetime(
        2026,
        9,
        5,
        10,
        0,
        tzinfo=timezone.utc,
    )
    end = datetime(
        2026,
        9,
        5,
        9,
        0,
        tzinfo=timezone.utc,
    )

    with pytest.raises(
        ValueError,
        match="ended_at",
    ):
        Meeting(
            meeting_id="meeting-1",
            tenant_id="tenant-1",
            title="Réunion",
            created_by="user-1",
            started_at=start,
            ended_at=end,
        )


def test_participant_is_tenant_and_meeting_scoped():
    participant = Participant(
        participant_id="participant-1",
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        display_name="Awa Dossou",
        role="Directrice",
    )

    assert participant.meeting_id == "meeting-1"
    assert participant.tenant_id == "tenant-1"
    assert participant.display_name == "Awa Dossou"


def test_transcript_segment_keeps_source_timing():
    segment = TranscriptSegment(
        segment_id="segment-1",
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        speaker_id="participant-1",
        text="Nous validons le lancement du pilote.",
        start_seconds=12.4,
        end_seconds=17.8,
        confidence=0.97,
    )

    assert segment.start_seconds == 12.4
    assert segment.end_seconds == 17.8
    assert segment.confidence == 0.97


def test_transcript_segment_rejects_invalid_confidence():
    with pytest.raises(
        ValueError,
        match="confidence",
    ):
        TranscriptSegment(
            segment_id="segment-1",
            meeting_id="meeting-1",
            tenant_id="tenant-1",
            text="Texte",
            start_seconds=0,
            end_seconds=1,
            confidence=1.5,
        )


def test_decision_requires_source_segment():
    decision = Decision(
        decision_id="decision-1",
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        text="Lancer le pilote en octobre.",
        source_segment_id="segment-4",
        status=DecisionStatus.VALIDATED,
    )

    assert decision.source_segment_id == "segment-4"
    assert decision.status == DecisionStatus.VALIDATED


def test_action_item_supports_assignee_due_date_and_status():
    due_at = datetime(
        2026,
        10,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    action = ActionItem(
        action_id="action-1",
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        title="Préparer le dossier pilote",
        source_segment_id="segment-5",
        assignee_id="participant-1",
        due_at=due_at,
        status=ActionStatus.IN_PROGRESS,
    )

    assert action.assignee_id == "participant-1"
    assert action.due_at == due_at
    assert action.status == ActionStatus.IN_PROGRESS
