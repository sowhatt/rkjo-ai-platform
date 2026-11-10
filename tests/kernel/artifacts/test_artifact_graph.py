import pytest

from rkjo_kernel.artifacts.graph import ArtifactGraph
from rkjo_kernel.artifacts.models import Artifact, ArtifactModality
from rkjo_kernel.artifacts.relations import ArtifactRelationType, relate


def item(identifier, tenant="tenant-a", mission="mission-1", trace="trace-1"):
    return Artifact(
        artifact_id=identifier,
        modality=ArtifactModality.DOCUMENT,
        tenant_id=tenant,
        mission_id=mission,
        trace_id=trace,
        content="data",
    )


def test_graph_traverses_multimodal_lineage():
    graph = ArtifactGraph()
    pdf, page, ocr, extraction = [item(i) for i in ("pdf", "page", "ocr", "extraction")]
    for artifact in (pdf, page, ocr, extraction):
        graph.add_artifact(artifact)
    for parent, child in ((pdf, page), (page, ocr), (ocr, extraction)):
        graph.add_relation(relate(parent=parent, child=child, relation_type=ArtifactRelationType.DERIVED_FROM))
    assert graph.children(tenant_id="tenant-a", artifact_id="pdf") == ("page",)
    assert graph.parents(tenant_id="tenant-a", artifact_id="ocr") == ("page",)
    assert graph.descendants(tenant_id="tenant-a", artifact_id="pdf") == ("page", "ocr", "extraction")
    assert graph.ancestors(tenant_id="tenant-a", artifact_id="extraction") == ("ocr", "page", "pdf")


def test_graph_rejects_cycles():
    graph = ArtifactGraph()
    a, b, c = [item(i) for i in ("a", "b", "c")]
    for artifact in (a, b, c):
        graph.add_artifact(artifact)
    graph.add_relation(relate(parent=a, child=b, relation_type=ArtifactRelationType.DERIVED_FROM))
    graph.add_relation(relate(parent=b, child=c, relation_type=ArtifactRelationType.DERIVED_FROM))
    with pytest.raises(ValueError, match="cycle"):
        graph.add_relation(relate(parent=c, child=a, relation_type=ArtifactRelationType.DERIVED_FROM))


def test_graph_isolates_tenants():
    graph = ArtifactGraph()
    graph.add_artifact(item("same", tenant="tenant-a"))
    graph.add_artifact(item("same", tenant="tenant-b"))
    assert graph.descendants(tenant_id="tenant-a", artifact_id="same") == ()
    with pytest.raises(KeyError):
        graph.ancestors(tenant_id="tenant-c", artifact_id="same")
    with pytest.raises(ValueError):
        graph.add_relation(
            relate(
                parent=item("same", tenant="tenant-a"),
                child=item("missing", tenant="tenant-a"),
                relation_type=ArtifactRelationType.DERIVED_FROM,
            )
        )


def test_graph_rejects_forged_relation_identity():
    from rkjo_kernel.artifacts.relations import ArtifactRelation
    graph = ArtifactGraph()
    graph.add_artifact(item("a"))
    graph.add_artifact(item("b"))
    with pytest.raises(ValueError, match="identity"):
        graph.add_relation(ArtifactRelation(
            parent_artifact_id="a",
            child_artifact_id="b",
            tenant_id="tenant-a",
            mission_id="other",
            trace_id="trace-1",
            relation_type=ArtifactRelationType.DERIVED_FROM,
        ))
