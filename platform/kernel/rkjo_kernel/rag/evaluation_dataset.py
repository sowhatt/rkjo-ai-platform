"""Load deterministic RAG evaluation datasets."""

from __future__ import annotations

import json
from pathlib import Path

from rkjo_kernel.rag.evaluation_models import (
    RAGEvaluationCase,
)


def load_evaluation_dataset(
    path: str | Path,
) -> list[RAGEvaluationCase]:
    dataset_path = Path(path)

    payload = json.loads(
        dataset_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        list,
    ):
        raise ValueError(
            "Evaluation dataset must be a JSON array."
        )

    cases: list[RAGEvaluationCase] = []

    for item in payload:
        if not isinstance(
            item,
            dict,
        ):
            raise ValueError(
                "Each evaluation case must be an object."
            )

        cases.append(
            RAGEvaluationCase(
                case_id=str(
                    item["case_id"]
                ),
                question=str(
                    item["question"]
                ),
                expected_document_ids=tuple(
                    item.get(
                        "expected_document_ids",
                        [],
                    )
                ),
                expected_concepts=tuple(
                    item.get(
                        "expected_concepts",
                        [],
                    )
                ),
                expect_answerable=bool(
                    item.get(
                        "expect_answerable",
                        True,
                    )
                ),
                limit=int(
                    item.get(
                        "limit",
                        5,
                    )
                ),
            )
        )

    return cases
