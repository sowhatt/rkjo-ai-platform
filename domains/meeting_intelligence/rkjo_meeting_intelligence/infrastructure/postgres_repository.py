"""PostgreSQL persistence for RKJO Meeting Intelligence."""

from __future__ import annotations

import psycopg

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


class PostgresMeetingRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty.")
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meeting_intelligence_meetings (
                    tenant_id TEXT NOT NULL,
                    meeting_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scheduled_at TIMESTAMPTZ,
                    started_at TIMESTAMPTZ,
                    ended_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (tenant_id, meeting_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meeting_intelligence_participants (
                    tenant_id TEXT NOT NULL,
                    meeting_id TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT,
                    email TEXT,
                    PRIMARY KEY (tenant_id, meeting_id, participant_id),
                    FOREIGN KEY (tenant_id, meeting_id)
                        REFERENCES meeting_intelligence_meetings(tenant_id, meeting_id)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meeting_intelligence_transcript_segments (
                    tenant_id TEXT NOT NULL,
                    meeting_id TEXT NOT NULL,
                    segment_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    start_seconds DOUBLE PRECISION NOT NULL,
                    end_seconds DOUBLE PRECISION NOT NULL,
                    speaker_id TEXT,
                    confidence DOUBLE PRECISION,
                    PRIMARY KEY (tenant_id, meeting_id, segment_id),
                    FOREIGN KEY (tenant_id, meeting_id)
                        REFERENCES meeting_intelligence_meetings(tenant_id, meeting_id)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meeting_intelligence_decisions (
                    tenant_id TEXT NOT NULL,
                    meeting_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_segment_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, meeting_id, decision_id),
                    FOREIGN KEY (tenant_id, meeting_id)
                        REFERENCES meeting_intelligence_meetings(tenant_id, meeting_id)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meeting_intelligence_actions (
                    tenant_id TEXT NOT NULL,
                    meeting_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_segment_id TEXT NOT NULL,
                    assignee_id TEXT,
                    due_at TIMESTAMPTZ,
                    status TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, meeting_id, action_id),
                    FOREIGN KEY (tenant_id, meeting_id)
                        REFERENCES meeting_intelligence_meetings(tenant_id, meeting_id)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_meeting_status ON meeting_intelligence_meetings (tenant_id, status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_action_due_at ON meeting_intelligence_actions (tenant_id, status, due_at)"
            )

    def save(self, meeting: Meeting) -> Meeting:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO meeting_intelligence_meetings (
                    tenant_id, meeting_id, title, created_by, status,
                    scheduled_at, started_at, ended_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, meeting_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    created_by = EXCLUDED.created_by,
                    status = EXCLUDED.status,
                    scheduled_at = EXCLUDED.scheduled_at,
                    started_at = EXCLUDED.started_at,
                    ended_at = EXCLUDED.ended_at,
                    updated_at = NOW()
                """,
                (
                    meeting.tenant_id, meeting.meeting_id, meeting.title,
                    meeting.created_by, meeting.status.value,
                    meeting.scheduled_at, meeting.started_at, meeting.ended_at,
                ),
            )
        return meeting

    def get(self, *, tenant_id: str, meeting_id: str) -> Meeting | None:
        tenant_id = tenant_id.strip()
        meeting_id = meeting_id.strip()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT title, created_by, status, scheduled_at, started_at, ended_at
                FROM meeting_intelligence_meetings
                WHERE tenant_id = %s AND meeting_id = %s
                """,
                (tenant_id, meeting_id),
            ).fetchone()
        if row is None:
            return None
        return Meeting(
            meeting_id=meeting_id,
            tenant_id=tenant_id,
            title=row[0],
            created_by=row[1],
            status=MeetingStatus(row[2]),
            scheduled_at=row[3],
            started_at=row[4],
            ended_at=row[5],
        )

    def list_for_tenant(self, *, tenant_id: str) -> list[Meeting]:
        tenant_id = tenant_id.strip()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT meeting_id, title, created_by, status,
                       scheduled_at, started_at, ended_at
                FROM meeting_intelligence_meetings
                WHERE tenant_id = %s
                ORDER BY scheduled_at DESC NULLS LAST, meeting_id
                """,
                (tenant_id,),
            ).fetchall()
        return [
            Meeting(
                meeting_id=row[0], tenant_id=tenant_id, title=row[1],
                created_by=row[2], status=MeetingStatus(row[3]),
                scheduled_at=row[4], started_at=row[5], ended_at=row[6],
            )
            for row in rows
        ]

    def save_participant(self, participant: Participant) -> Participant:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO meeting_intelligence_participants
                    (tenant_id, meeting_id, participant_id, display_name, role, email)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, meeting_id, participant_id)
                DO UPDATE SET display_name = EXCLUDED.display_name,
                              role = EXCLUDED.role,
                              email = EXCLUDED.email
                """,
                (participant.tenant_id, participant.meeting_id, participant.participant_id,
                 participant.display_name, participant.role, participant.email),
            )
        return participant

    def list_participants(self, *, tenant_id: str, meeting_id: str) -> list[Participant]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT participant_id, display_name, role, email
                FROM meeting_intelligence_participants
                WHERE tenant_id = %s AND meeting_id = %s
                ORDER BY display_name, participant_id
                """,
                (tenant_id.strip(), meeting_id.strip()),
            ).fetchall()
        return [Participant(row[0], meeting_id.strip(), tenant_id.strip(), row[1], row[2], row[3]) for row in rows]

    def save_transcript_segment(self, segment: TranscriptSegment) -> TranscriptSegment:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO meeting_intelligence_transcript_segments
                    (tenant_id, meeting_id, segment_id, text, start_seconds,
                     end_seconds, speaker_id, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, meeting_id, segment_id)
                DO UPDATE SET text = EXCLUDED.text,
                              start_seconds = EXCLUDED.start_seconds,
                              end_seconds = EXCLUDED.end_seconds,
                              speaker_id = EXCLUDED.speaker_id,
                              confidence = EXCLUDED.confidence
                """,
                (segment.tenant_id, segment.meeting_id, segment.segment_id, segment.text,
                 segment.start_seconds, segment.end_seconds, segment.speaker_id, segment.confidence),
            )
        return segment

    def list_transcript_segments(self, *, tenant_id: str, meeting_id: str) -> list[TranscriptSegment]:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT segment_id, text, start_seconds, end_seconds, speaker_id, confidence
                FROM meeting_intelligence_transcript_segments
                WHERE tenant_id = %s AND meeting_id = %s
                ORDER BY start_seconds, segment_id
                """,
                (tenant_id, meeting_id),
            ).fetchall()
        return [TranscriptSegment(row[0], meeting_id, tenant_id, row[1], row[2], row[3], row[4], row[5]) for row in rows]

    def save_decision(self, decision: Decision) -> Decision:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO meeting_intelligence_decisions
                    (tenant_id, meeting_id, decision_id, text, source_segment_id, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, meeting_id, decision_id)
                DO UPDATE SET text = EXCLUDED.text,
                              source_segment_id = EXCLUDED.source_segment_id,
                              status = EXCLUDED.status
                """,
                (decision.tenant_id, decision.meeting_id, decision.decision_id,
                 decision.text, decision.source_segment_id, decision.status.value),
            )
        return decision

    def list_decisions(self, *, tenant_id: str, meeting_id: str) -> list[Decision]:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT decision_id, text, source_segment_id, status
                FROM meeting_intelligence_decisions
                WHERE tenant_id = %s AND meeting_id = %s
                ORDER BY decision_id
                """,
                (tenant_id, meeting_id),
            ).fetchall()
        return [Decision(row[0], meeting_id, tenant_id, row[1], row[2], DecisionStatus(row[3])) for row in rows]

    def save_action(self, action: ActionItem) -> ActionItem:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO meeting_intelligence_actions
                    (tenant_id, meeting_id, action_id, title, source_segment_id,
                     assignee_id, due_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, meeting_id, action_id)
                DO UPDATE SET title = EXCLUDED.title,
                              source_segment_id = EXCLUDED.source_segment_id,
                              assignee_id = EXCLUDED.assignee_id,
                              due_at = EXCLUDED.due_at,
                              status = EXCLUDED.status
                """,
                (action.tenant_id, action.meeting_id, action.action_id, action.title,
                 action.source_segment_id, action.assignee_id, action.due_at, action.status.value),
            )
        return action

    def list_actions(self, *, tenant_id: str, meeting_id: str) -> list[ActionItem]:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT action_id, title, source_segment_id, assignee_id, due_at, status
                FROM meeting_intelligence_actions
                WHERE tenant_id = %s AND meeting_id = %s
                ORDER BY due_at NULLS LAST, action_id
                """,
                (tenant_id, meeting_id),
            ).fetchall()
        return [ActionItem(row[0], meeting_id, tenant_id, row[1], row[2], row[3], row[4], ActionStatus(row[5])) for row in rows]
