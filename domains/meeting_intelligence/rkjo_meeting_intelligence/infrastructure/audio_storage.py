"""Audio object storage abstractions for RKJO Meeting Intelligence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class AudioStorage(Protocol):
    def save(
        self,
        *,
        tenant_id: str,
        meeting_id: str,
        asset_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        """Persist one audio object and return its storage key."""
        ...

    def read(self, *, storage_key: str) -> bytes:
        """Load one previously persisted media object."""
        ...


class LocalAudioStorage:
    """Filesystem storage for local development and tests."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        *,
        tenant_id: str,
        meeting_id: str,
        asset_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        if not content:
            raise ValueError("audio content must not be empty.")

        safe_name = Path(filename).name or "audio.bin"
        relative = Path(tenant_id) / meeting_id / asset_id / safe_name
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative.as_posix()

    def read(self, *, storage_key: str) -> bytes:
        relative = Path(storage_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("storage_key must be relative to the audio root.")
        target = (self.root / relative).resolve()
        if self.root not in target.parents:
            raise ValueError("storage_key escapes the audio root.")
        return target.read_bytes()
