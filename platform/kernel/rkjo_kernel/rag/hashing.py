from __future__ import annotations

import hashlib


def compute_content_hash(content: str) -> str:
    if not content.strip():
        raise ValueError(
            "Content to hash must not be empty."
        )

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()
