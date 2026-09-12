"""In-memory Meeting repository used by fast unit/API tests."""

from __future__ import annotations

from rkjo_meeting_intelligence.domain.models import (
    ActionItem,
    Decision,
    Meeting,
    Participant,
    TranscriptSegment,
)


class InMemoryMeetingRepository:
    def __init__(self) -> None:
        self._meetings: dict[tuple[str, str], Meeting] = {}
        self._participants: dict[tuple[str, str, str], Participant] = {}
        self._segments: dict[tuple[str, str, str], TranscriptSegment] = {}
        self._decisions: dict[tuple[str, str, str], Decision] = {}
        self._actions: dict[tuple[str, str, str], ActionItem] = {}

    def save(self, meeting: Meeting) -> Meeting:
        self._meetings[(meeting.tenant_id, meeting.meeting_id)] = meeting
        return meeting

    def get(self, *, tenant_id: str, meeting_id: str) -> Meeting | None:
        return self._meetings.get((tenant_id.strip(), meeting_id.strip()))

    def list_for_tenant(self, *, tenant_id: str) -> list[Meeting]:
        tenant_id = tenant_id.strip()
        return sorted(
            [meeting for (stored_tenant_id, _), meeting in self._meetings.items() if stored_tenant_id == tenant_id],
            key=lambda meeting: meeting.meeting_id,
        )

    def save_participant(self, participant: Participant) -> Participant:
        self._participants[(participant.tenant_id, participant.meeting_id, participant.participant_id)] = participant
        return participant

    def list_participants(self, *, tenant_id: str, meeting_id: str) -> list[Participant]:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip()
        return sorted(
            [item for (t, m, _), item in self._participants.items() if t == tenant_id and m == meeting_id],
            key=lambda item: item.display_name,
        )

    def save_transcript_segment(self, segment: TranscriptSegment) -> TranscriptSegment:
        self._segments[(segment.tenant_id, segment.meeting_id, segment.segment_id)] = segment
        return segment

    def list_transcript_segments(self, *, tenant_id: str, meeting_id: str) -> list[TranscriptSegment]:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip()
        return sorted(
            [item for (t, m, _), item in self._segments.items() if t == tenant_id and m == meeting_id],
            key=lambda item: (item.start_seconds, item.segment_id),
        )

    def save_decision(self, decision: Decision) -> Decision:
        self._decisions[(decision.tenant_id, decision.meeting_id, decision.decision_id)] = decision
        return decision

    def list_decisions(self, *, tenant_id: str, meeting_id: str) -> list[Decision]:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip()
        return sorted(
            [item for (t, m, _), item in self._decisions.items() if t == tenant_id and m == meeting_id],
            key=lambda item: item.decision_id,
        )

    def save_action(self, action: ActionItem) -> ActionItem:
        self._actions[(action.tenant_id, action.meeting_id, action.action_id)] = action
        return action

    def list_actions(self, *, tenant_id: str, meeting_id: str) -> list[ActionItem]:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip()
        return sorted(
            [item for (t, m, _), item in self._actions.items() if t == tenant_id and m == meeting_id],
            key=lambda item: (item.due_at is None, item.due_at, item.action_id),
        )
