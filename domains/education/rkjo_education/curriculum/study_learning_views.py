"""Source-grounded, deterministic revision views for the B+D student pilot.

No LLM, external API or persistence: these are extracted study notes and a
navigable page/concept outline, not an expert-authored synthesis.
"""
from __future__ import annotations

import re

from rkjo_education.curriculum.study_sources import StudySourcePackage


def _compact(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit].rstrip()


def build_study_views(source: StudySourcePackage, *, max_pages: int = 20) -> dict:
    if max_pages < 1 or max_pages > 50:
        raise ValueError("max_pages must be between 1 and 50")
    notes = []
    branches = []
    for segment in source.segments[:max_pages]:
        lines = [line.strip() for line in segment.text.splitlines() if line.strip()]
        if not lines:
            continue
        # A title is used only when literally present on the PDF page;
        # otherwise it is visibly labelled as a page, not invented as a concept.
        candidate = next((line for line in lines[:4] if 3 <= len(line) <= 100), "")
        heading = _compact(candidate, 100) if candidate else f"Page {segment.page}"
        fragments = re.split(r"(?<=[.!?])\s+|\n+", segment.text)
        excerpts = []
        for fragment in fragments:
            excerpt = _compact(fragment, 340)
            if len(excerpt) >= 20 and excerpt not in excerpts:
                excerpts.append(excerpt)
            if len(excerpts) == 3:
                break
        if not excerpts:
            excerpts = [_compact(segment.text, 340)]
        citation = {"page": segment.page, "segment_id": segment.segment_id}
        notes.append({
            "title": heading, "excerpts": excerpts,
            "citation": citation, "source_only": True,
        })
        branches.append({
            "id": segment.segment_id, "label": heading,
            "page": segment.page, "children": [
                {"label": text[:100], "text": text, "citation": citation}
                for text in excerpts
            ],
        })
    if not notes:
        raise ValueError("No usable text for revision views")
    return {
        "revision_notes": notes,
        "mind_map": {
            "root": source.ue_id,
            "branches": branches,
            "representation": "source_outline",
        },
        "generation_mode": "deterministic_excerpts",
        "disclaimer": "Extraits du PDF, pas une synthèse IA ni une carte conceptuelle validée.",
    }
