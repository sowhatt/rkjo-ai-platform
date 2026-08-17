import json

from rkjo_kernel.rag.retrieval_evaluation_dataset import (
    load_retrieval_evaluation_dataset,
)


def test_load_retrieval_dataset(
    tmp_path,
):
    path = tmp_path / "dataset.json"

    path.write_text(
        json.dumps(
            [
                {
                    "case_id": "case",
                    "query": "REF123",
                    "expected_document_id": "doc",
                    "limit": 3
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = (
        load_retrieval_evaluation_dataset(
            path
        )
    )

    assert len(cases) == 1
    assert cases[0].query == "REF123"
    assert (
        cases[0].expected_document_id
        == "doc"
    )
    assert cases[0].limit == 3
