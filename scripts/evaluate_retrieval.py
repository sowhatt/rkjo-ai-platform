#!/usr/bin/env python3
"""Run retrieval-only RKJO benchmarks."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rkjo_api.dependencies import (
    get_rag_search_service,
)
from rkjo_kernel.rag.retrieval_evaluation import (
    RetrievalEvaluationHarness,
)
from rkjo_kernel.rag.retrieval_evaluation_dataset import (
    load_retrieval_evaluation_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dataset",
        required=True,
    )

    parser.add_argument(
        "--output",
        default=None,
    )

    args = parser.parse_args()

    cases = (
        load_retrieval_evaluation_dataset(
            args.dataset
        )
    )

    harness = RetrievalEvaluationHarness(
        search_service=(
            get_rag_search_service()
        )
    )

    report = harness.evaluate(
        cases
    )

    rendered = json.dumps(
        asdict(report),
        ensure_ascii=False,
        indent=2,
    )

    print(rendered)

    if args.output:
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
