from types import SimpleNamespace

import pytest

from rkjo_kernel.rag.openai_embedding import (
    OpenAIEmbeddingProvider,
)


class FakeEmbeddings:

    def __init__(
        self,
        *,
        dimensions=4,
    ):
        self.dimensions = dimensions
        self.calls = []

    def create(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)

        inputs = kwargs["input"]

        if isinstance(inputs, str):
            inputs = [inputs]

        data = []

        for index, _ in enumerate(inputs):
            data.append(
                SimpleNamespace(
                    index=index,
                    embedding=[
                        float(index + 1)
                        for _ in range(
                            self.dimensions
                        )
                    ],
                )
            )

        return SimpleNamespace(
            data=data
        )


class FakeOpenAI:

    def __init__(
        self,
        *,
        dimensions=4,
    ):
        self.embeddings = FakeEmbeddings(
            dimensions=dimensions
        )


def make_provider(
    *,
    dimensions=4,
):
    return OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        dimensions=dimensions,
        client=FakeOpenAI(
            dimensions=dimensions
        ),
    )


def test_embed_returns_vector():
    provider = make_provider()

    vector = provider.embed(
        "soil rainfall"
    )

    assert len(vector) == 4


def test_embed_passes_model_and_dimensions():
    provider = make_provider()

    provider.embed(
        "agriculture"
    )

    call = (
        provider.client
        .embeddings
        .calls[0]
    )

    assert (
        call["model"]
        == "text-embedding-3-small"
    )

    assert call[
        "dimensions"
    ] == 4

    assert call[
        "encoding_format"
    ] == "float"


def test_empty_text_is_rejected():
    provider = make_provider()

    with pytest.raises(
        ValueError,
        match="empty",
    ):
        provider.embed(" ")


def test_batch_embedding_preserves_order():
    provider = make_provider()

    vectors = provider.embed_batch(
        [
            "one",
            "two",
            "three",
        ]
    )

    assert len(vectors) == 3

    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0
    assert vectors[2][0] == 3.0


def test_dimension_mismatch_is_rejected():
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        dimensions=4,
        client=FakeOpenAI(
            dimensions=3
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="dimension mismatch",
    ):
        provider.embed(
            "knowledge"
        )
