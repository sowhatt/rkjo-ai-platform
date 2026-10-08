"""In-memory, tenant-isolated artifact lineage graph."""

from __future__ import annotations

from collections import deque

from rkjo_kernel.artifacts.models import Artifact
from rkjo_kernel.artifacts.relations import ArtifactRelation


class ArtifactGraph:
    def __init__(self) -> None:
        self._artifacts: dict[tuple[str, str], Artifact] = {}
        self._relations: dict[str, list[ArtifactRelation]] = {}

    def add_artifact(self, artifact: Artifact) -> None:
        key = (artifact.tenant_id, artifact.artifact_id)
        existing = self._artifacts.get(key)
        if existing is not None and existing != artifact:
            raise ValueError("Artifact identity already exists with different content.")
        self._artifacts[key] = artifact

    def add_relation(self, relation: ArtifactRelation) -> None:
        tenant = relation.tenant_id
        parent = self._artifacts.get((tenant, relation.parent_artifact_id))
        child = self._artifacts.get((tenant, relation.child_artifact_id))
        if parent is None or child is None:
            raise ValueError("Both relation endpoints must exist in the same tenant.")
        if parent.mission_id != child.mission_id or parent.trace_id != child.trace_id:
            raise ValueError("Artifact relation identity mismatch.")
        if relation.mission_id != parent.mission_id or relation.trace_id != parent.trace_id:
            raise ValueError("Relation identity does not match artifacts.")
        if relation.parent_artifact_id == relation.child_artifact_id:
            raise ValueError("Self-referencing artifact relation.")
        relations = self._relations.setdefault(tenant, [])
        if relation in relations:
            return
        if relation.parent_artifact_id in self.descendants(
            tenant_id=tenant, artifact_id=relation.child_artifact_id
        ):
            raise ValueError("Artifact lineage cycle detected.")
        relations.append(relation)

    def children(self, *, tenant_id: str, artifact_id: str) -> tuple[str, ...]:
        self._require(tenant_id, artifact_id)
        return tuple(dict.fromkeys(
            r.child_artifact_id for r in self._relations.get(tenant_id, [])
            if r.parent_artifact_id == artifact_id
        ))

    def parents(self, *, tenant_id: str, artifact_id: str) -> tuple[str, ...]:
        self._require(tenant_id, artifact_id)
        return tuple(dict.fromkeys(
            r.parent_artifact_id for r in self._relations.get(tenant_id, [])
            if r.child_artifact_id == artifact_id
        ))

    def descendants(self, *, tenant_id: str, artifact_id: str) -> tuple[str, ...]:
        return self._walk(tenant_id=tenant_id, artifact_id=artifact_id, forward=True)

    def ancestors(self, *, tenant_id: str, artifact_id: str) -> tuple[str, ...]:
        return self._walk(tenant_id=tenant_id, artifact_id=artifact_id, forward=False)

    def _require(self, tenant_id: str, artifact_id: str) -> None:
        if (tenant_id, artifact_id) not in self._artifacts:
            raise KeyError("Artifact not found for tenant.")

    def _walk(self, *, tenant_id: str, artifact_id: str, forward: bool) -> tuple[str, ...]:
        self._require(tenant_id, artifact_id)
        seen = {artifact_id}
        result: list[str] = []
        queue = deque([artifact_id])
        while queue:
            current = queue.popleft()
            neighbors = (
                self.children(tenant_id=tenant_id, artifact_id=current)
                if forward else self.parents(tenant_id=tenant_id, artifact_id=current)
            )
            for neighbor in neighbors:
                if neighbor not in seen:
                    seen.add(neighbor)
                    result.append(neighbor)
                    queue.append(neighbor)
        return tuple(result)
