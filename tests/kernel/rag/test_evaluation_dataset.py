import json

import pytest

from rkjo_kernel.rag.evaluation_dataset import (
    load_evaluation_dataset,
)


def test_load_dataset(tmp_path):
    path = tmp_path / "dataset.json"

    path.write_text(
        json.dumps(
            [
                {
                    "case_id": "case-1",
                    "question": "Question",
                    "expected_document_ids": [
                        "doc-1"
                    ],
                    "expected_concepts": [
                        "maïs"
                    ],
                    "limit": 3
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = load_evaluation_dataset(
        path
    )

    assert len(cases) == 1
    assert cases[0].case_id == "case-1"
    assert (
        cases[0].expected_document_ids
        == ("doc-1",)
    )
    assert cases[0].limit == 3


def test_dataset_must_be_array(
    tmp_path,
):
    path = tmp_path / "dataset.json"

    path.write_text(
        '{"case_id":"bad"}',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="JSON array",
    ):
        load_evaluation_dataset(
            path
        )
