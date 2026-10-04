from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from rkjo_education.events import EducationEventType, EducationLearningEvent

NBA_POLICY_VERSION = "v2.3-policy-v1"

class NextBestActionType(StrEnum):
    POSITIONING_TEST="positioning_test"
    EXPLAIN_CONCEPT="explain_concept"
    REEXPLAIN_DIFFERENTLY="reexplain_differently"
    REMEDIATE="remediate"
    PRACTICE_SIMILAR="practice_similar"
    PRACTICE_PREREQUISITE="practice_prerequisite"
    INCREASE_DIFFICULTY="increase_difficulty"
    PRACTICE_TIMED="practice_timed"
    REQUEST_PROOF="request_proof"
    REVIEW="review"
    ADVANCE="advance"
    START_MOCK_EXAM="start_mock_exam"
    MARK_FOR_REVIEW="mark_for_review"
    ASK_FOR_HUMAN_HELP="ask_for_human_help"
    NEXT_ACTIVITY="next_activity"
    CONSOLIDATION="consolidation"
    CONSOLIDATION_AND_ALERT="consolidation_and_alert"

@dataclass(frozen=True, slots=True)
class CompetencySignal:
    competency_code: str
    mastery: float
    autonomy: float = 1.0
    retention: float = 1.0
    importance: int = 1
    covered_by_exam: bool = True
    prerequisite_code: str | None = None
    prerequisite_mastery: float | None = None
    latest_correct: bool | None = None
    latest_help: float = 0.0
    latest_proof: str | None = None
    consecutive_failures: int = 0
    consecutive_no_hint_successes: int = 0
    distinct_success_exercises: int = 0
    remediation_count: int = 0
    remediation_mastery_gain: float = 1.0
    valid_proof: bool = False
    seen: bool = True
    eligible: bool = True

@dataclass(frozen=True, slots=True)
class NBAContext:
    competencies: tuple[CompetencySignal, ...] = ()
    target_competency: str | None = None
    exam_days_remaining: int | None = None
    tester_share_last_24h: float = 1.0
    mock_exam_last_24h: bool = True

@dataclass(frozen=True, slots=True)
class NextBestAction:
    action: NextBestActionType
    reason: str
    rule_id: str = "legacy"
    target_competency: str | None = None
    modifiers: tuple[str, ...] = ()
    policy_version: str = NBA_POLICY_VERSION
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signals: dict[str, object] = field(default_factory=dict)
    secondary_action: NextBestActionType | None = None
    @property
    def explanation(self) -> str:
        return self.reason

class NextBestActionService:
    @staticmethod
    def repeated_failures(events: Iterable[EducationLearningEvent], *, competency_code: str) -> int:
        count=0
        for event in reversed(list(events)):
            if event.competency_code != competency_code or event.event_type != EducationEventType.ANSWER_SUBMITTED: continue
            if event.payload.get("correct") is True: break
            if event.payload.get("correct") is False: count += 1
        return count

    @staticmethod
    def _d(action, rule, target, reason, modifiers=(), secondary=None, extra=None):
        signals={}
        if target:
            signals={"mastery":target.mastery,"autonomy":target.autonomy,"retention":target.retention,"latest_correct":target.latest_correct,"latest_help":target.latest_help,"latest_proof":target.latest_proof,"consecutive_failures":target.consecutive_failures}
        signals.update(extra or {})
        return NextBestAction(action, reason, rule, target.competency_code if target else None, tuple(modifiers), NBA_POLICY_VERSION, datetime.now(timezone.utc), signals, secondary)

    def decide_context(self, context: NBAContext) -> NextBestAction:
        scope=tuple(x for x in context.competencies if x.seen and x.eligible)
        if context.exam_days_remaining is not None and context.exam_days_remaining <= 3:
            scope=tuple(x for x in scope if x.covered_by_exam)
        target=next((x for x in scope if x.competency_code==context.target_competency), scope[0] if scope else None)
        mods=[]
        if context.exam_days_remaining is not None and context.exam_days_remaining <= 3:
            mods.append("M2")
            if not context.mock_exam_last_24h:
                return self._d(NextBestActionType.START_MOCK_EXAM,"R6",target,"Examen imminent : commencer par une simulation réaliste.",mods,extra={"exam_days_remaining":context.exam_days_remaining,"mock_exam_last_24h":False})
        elif context.exam_days_remaining is not None and context.exam_days_remaining <= 15: mods.append("M1")
        if target is None or (target.latest_correct is None and target.latest_proof is None):
            return self._d(NextBestActionType.POSITIONING_TEST,"R0",target,"Aucune observation exploitable : commencer par un positionnement.",mods)
        if target.remediation_count >= 3 and target.remediation_mastery_gain < .05:
            return self._d(NextBestActionType.MARK_FOR_REVIEW,"R1",target,"Les remédiations n’améliorent plus suffisamment la maîtrise : marquer pour revue.",mods,NextBestActionType.ASK_FOR_HUMAN_HELP)
        if target.latest_proof=="failed": return self._d(NextBestActionType.REMEDIATE,"R2",target,"La preuve autonome a échoué : consolider avant une nouvelle preuve.",mods)
        if target.mastery < .40 and target.prerequisite_code and target.prerequisite_mastery is not None and target.prerequisite_mastery < .50 and not ("M2" in mods and target.importance < 3):
            p=CompetencySignal(target.prerequisite_code,target.prerequisite_mastery,latest_correct=False)
            return self._d(NextBestActionType.PRACTICE_PREREQUISITE,"R3",p,"Un prérequis fragile bloque la compétence cible.",mods,extra={"blocked_competency":target.competency_code})
        if target.consecutive_failures >= 2: return self._d(NextBestActionType.REEXPLAIN_DIFFERENTLY,"R4",target,"Deux échecs consécutifs : réexpliquer autrement puis réduire la difficulté.",mods,extra={"difficulty_delta":-1})
        if target.latest_correct is False: return self._d(NextBestActionType.REMEDIATE,"R5",target,"Premier échec : explication ciblée puis exercice similaire.",mods)
        review=min((x for x in scope if x.mastery>=.40 and x.retention<.60),key=lambda x:(x.retention,-x.importance),default=None)
        if review: return self._d(NextBestActionType.REVIEW,"R6",review,"Une compétence déjà travaillée doit être réactivée.",mods)
        if target.latest_help>=.5 or target.autonomy<.70:
            action=NextBestActionType.PRACTICE_TIMED if "M1" in mods and context.tester_share_last_24h<.40 else NextBestActionType.PRACTICE_SIMILAR
            return self._d(action,"R7",target,"La réussite reste trop assistée : pratiquer à nouveau.",mods)
        if target.consecutive_no_hint_successes>=3 and target.distinct_success_exercises>=3 and not target.valid_proof:
            return self._d(NextBestActionType.REQUEST_PROOF,"R8",target,"Trois réussites autonomes distinctes : vérifier par une preuve sans aide.",mods)
        if target.latest_proof=="passed" and target.retention>=.60:
            next_target=next((x for x in scope if x.competency_code != target.competency_code and x.eligible), target)
            return self._d(NextBestActionType.ADVANCE,"R9",next_target,"Preuve autonome réussie et rétention suffisante : avancer.",mods,extra={"completed_competency":target.competency_code})
        action=NextBestActionType.INCREASE_DIFFICULTY if target.latest_correct is True and target.latest_help==0 else NextBestActionType.PRACTICE_SIMILAR
        if action==NextBestActionType.PRACTICE_SIMILAR and "M1" in mods and context.tester_share_last_24h<.40: action=NextBestActionType.PRACTICE_TIMED
        return self._d(action,"R10",target,"Continuer avec l’action adaptée aux derniers signaux.",mods)

    def decide(self, *, correct: bool, autonomy_score: int, mastery: str, proof_required: bool, repeated_failures: int=0) -> NextBestAction:
        if not correct:
            if repeated_failures>=2: return NextBestAction(NextBestActionType.CONSOLIDATION_AND_ALERT,"Échecs répétés : consolidation et intervention professeur.")
            return NextBestAction(NextBestActionType.CONSOLIDATION,"Réponse incorrecte : consolider avant de poursuivre.")
        if proof_required or autonomy_score<70 or mastery in {"developing","provisional"}: return NextBestAction(NextBestActionType.REQUEST_PROOF,"Réussite à confirmer par une preuve autonome.")
        return NextBestAction(NextBestActionType.NEXT_ACTIVITY,"Réussite autonome : poursuivre vers l’activité suivante.")
