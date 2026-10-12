import pytest

from rkjo_education.curriculum.study_media_intake import (
    BOOK_MAX_BYTES, IntakeState, SourceKind, SourceLanguage, StudyMediaRequest,
)


def book(**changes):
    args = dict(
        tenant_id="univ-a", learner_id="learner-1", ue_id="physiologie",
        kind=SourceKind.DIGITAL_BOOK, filename="textbook.pdf",
        size_bytes=BOOK_MAX_BYTES, content_type="application/pdf",
        language=SourceLanguage.ENGLISH, translation_to_french=True,
        rights_confirmed=True,
    )
    args.update(changes)
    return StudyMediaRequest(**args)


def audio(**changes):
    args = dict(
        tenant_id="univ-a", learner_id="learner-1", ue_id="physiologie",
        kind=SourceKind.LECTURE_AUDIO, filename="cm.m4a",
        size_bytes=12_000_000, content_type="audio/mp4",
        language=SourceLanguage.FRENCH, rights_confirmed=True,
        recording_consent_confirmed=True,
    )
    args.update(changes)
    return StudyMediaRequest(**args)


def test_book_50_mib_english_translation_request():
    obj = book()
    assert obj.size_bytes == 50 * 1024 * 1024
    assert obj.translation_to_french
    assert obj.initial_state is IntakeState.AWAITING_EXTRACTION


def test_audio_requires_transcription():
    assert audio().initial_state is IntakeState.AWAITING_TRANSCRIPTION


@pytest.mark.parametrize("size", [0, BOOK_MAX_BYTES + 1, -10])
def test_reject_invalid_book_size(size):
    with pytest.raises(ValueError, match="50 MiB"):
        book(size_bytes=size)


def test_reject_unsupported_book_format():
    with pytest.raises(ValueError, match="PDF or EPUB"):
        book(content_type="text/plain")


def test_audio_requires_recording_permission():
    with pytest.raises(ValueError, match="Recording permission"):
        audio(recording_consent_confirmed=False)


def test_material_rights_are_required():
    with pytest.raises(ValueError, match="Right to use"):
        book(rights_confirmed=False)


def test_translation_requires_english_source():
    with pytest.raises(ValueError, match="English"):
        book(language=SourceLanguage.FRENCH)


@pytest.mark.parametrize("mime", ["application/pdf", "video/mp4"])
def test_unsupported_audio_formats(mime):
    with pytest.raises(ValueError, match="audio type"):
        audio(content_type=mime)


def test_epub_book_is_supported():
    assert book(content_type="application/epub+zip").kind is SourceKind.DIGITAL_BOOK
