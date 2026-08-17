"""Load retrieval-only evaluation datasets."""

from __future__ import annotations

import json
from pathlib import Path

from rkjo_kernel.rag.retrieval_evaluation import (
    RetrievalEvaluationCase,
)


def load_retrieval_evaluation_dataset(
    path: str | Path,
) -> list[RetrievalEvaluationCase]:
    dataset_path = Path(path)

    payload = json.loads(
        dataset_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, list):
        raise ValueError(
            "Retrieval evaluation dataset "
            "must be a JSON array."
        )

    return [
        RetrievalEvaluationCase(
            case_id=str(item["case_id"]),
            query=str(item["query"]),
            expected_document_id=str(
                item["expected_document_id"]
            ),
            limit=int(
                item.get("limit", 5)
            ),
        )
        for item in payload
    ]
