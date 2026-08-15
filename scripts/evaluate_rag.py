#!/usr/bin/env python3
"""Run the RKJO RAG baseline evaluation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from rkjo_api.dependencies import (
    get_rag_answering_service,
)
from rkjo_kernel.rag.evaluation import (
    RAGEvaluationHarness,
)
from rkjo_kernel.rag.evaluation_dataset import (
    load_evaluation_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dataset",
        default="evaluation/rag/baseline.json",
    )

    parser.add_argument(
        "--output",
        default=None,
    )

    args = parser.parse_args()

    cases = load_evaluation_dataset(
        args.dataset
    )

    harness = RAGEvaluationHarness(
        service=(
            get_rag_answering_service()
        )
    )

    report = harness.evaluate(
        cases
    )

    payload = asdict(report)

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )

    print(rendered)

    if args.output:
        from pathlib import Path

        output = Path(args.output)

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            rendered + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
