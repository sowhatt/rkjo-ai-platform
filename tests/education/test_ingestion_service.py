from uuid import uuid4
import pytest

from rkjo_education.ingestion import (
    DocumentKind,
    EducationIngestionService,
    Provenance,
)


def test_ingests_course_with_explicit_provenance():
    service = EducationIngestionService()
    doc = service.ingest(
        tenant_id=uuid4(),
        learner_id=uuid4(),
        filename="cours.pdf",
        media_type="application/pdf",
        extracted_text="  Cycle de Krebs  ",
        kind=DocumentKind.COURSE,
    )
    assert doc.extracted_text == "Cycle de Krebs"
    assert doc.kind == DocumentKind.COURSE
    assert doc.provenance == Provenance.LEARNER_UPLOAD
    assert len(doc.source_hash) == 64


def test_ingestion_rejects_empty_or_unsupported_content():
    service = EducationIngestionService()
    common = dict(tenant_id=uuid4(), learner_id=uuid4(), filename="x")
    with pytest.raises(ValueError):
        service.ingest(**common, media_type="audio/mp3", extracted_text="x", kind=DocumentKind.COURSE)
    with pytest.raises(ValueError):
        service.ingest(**common, media_type="text/plain", extracted_text=" ", kind=DocumentKind.TD)
