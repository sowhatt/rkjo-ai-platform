from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class CorrectedQuestionBlock:
    question_ref: str
    body: str
    earned_points: float | None = None
    max_points: float | None = None


class CorrectedCopySplitter:
    """Split a corrected copy question-by-question without inventing missing marks."""

    _question = re.compile(r"(?im)^\s*(?:question|q)\s*(\d+)\s*[:.)-]?\s*")
    _score = re.compile(r"(?i)(?:note\s*[:=]?\s*)?(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)")

    def split(self, text: str) -> list[CorrectedQuestionBlock]:
        source = text.strip()
        if not source:
            return []
        matches = list(self._question.finditer(source))
        if not matches:
            return [self._block("document", source)]
        blocks: list[CorrectedQuestionBlock] = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
            body = source[match.end():end].strip()
            if body:
                blocks.append(self._block(f"q{match.group(1)}", body))
        return blocks

    def _block(self, ref: str, body: str) -> CorrectedQuestionBlock:
        score = self._score.search(body)
        if score is None:
            return CorrectedQuestionBlock(question_ref=ref, body=body)
        earned = float(score.group(1).replace(",", "."))
        maximum = float(score.group(2).replace(",", "."))
        if maximum <= 0 or earned < 0 or earned > maximum:
            return CorrectedQuestionBlock(question_ref=ref, body=body)
        return CorrectedQuestionBlock(
            question_ref=ref,
            body=body,
            earned_points=earned,
            max_points=maximum,
        )
