from rkjo_kernel.llm.models import (
    LLMResponse,
)
from rkjo_kernel.rag.llm_generation import (
    LLMBackedAnswerGenerator,
    SYSTEM_PROMPT,
)


class FakeLLM:
    def __init__(self, content="Réponse fondée [1]."):
        self.content = content
        self.requests = []

    def generate(self, request):
        self.requests.append(request)

        return LLMResponse(
            content=self.content,
            provider="fake",
            model=request.model or "fake-model",
        )


def test_llm_backed_generator_uses_grounded_prompt_and_context():
    llm = FakeLLM()

    generator = LLMBackedAnswerGenerator(
        llm=llm,
        model="test-model",
    )

    answer = generator.generate(
        question="Question ?",
        context="[1]\nSource fiable.",
    )

    assert answer == "Réponse fondée [1]."

    request = llm.requests[0]

    assert request.model == "test-model"
    assert request.messages[0].role == "system"
    assert request.messages[0].content == SYSTEM_PROMPT
    assert request.messages[1].role == "user"
    assert "Question ?" in request.messages[1].content
    assert "Source fiable." in request.messages[1].content
    assert request.metadata["workload"] == "rag_answer_generation"


def test_llm_backed_generator_rejects_empty_question():
    generator = LLMBackedAnswerGenerator(
        llm=FakeLLM(),
    )

    try:
        generator.generate(
            question=" ",
            context="[1] source",
        )
    except ValueError as exc:
        assert "question" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_llm_backed_generator_rejects_empty_context():
    generator = LLMBackedAnswerGenerator(
        llm=FakeLLM(),
    )

    try:
        generator.generate(
            question="Question",
            context=" ",
        )
    except ValueError as exc:
        assert "context" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


class FakeGateway:
    def __init__(self):
        self.calls = []

    def generate(self, request, *, context):
        self.calls.append((request, context))
        return LLMResponse(
            content="Réponse gouvernée [1].",
            provider="ollama",
            model=request.model or "local-model",
        )


def test_llm_backed_generator_uses_gateway_execution_context():
    from rkjo_kernel.mission.execution_context import ExecutionContext

    gateway = FakeGateway()
    generator = LLMBackedAnswerGenerator(
        gateway=gateway,
    )
    execution_context = ExecutionContext(
        mission_id="rag-1",
        tenant_id="tenant-1",
        trace_id="trace-1",
    )

    answer = generator.generate(
        question="Question ?",
        context="[1] Source.",
        execution_context=execution_context,
    )

    assert answer == "Réponse gouvernée [1]."
    request, forwarded_context = gateway.calls[0]
    assert forwarded_context is execution_context
    assert request.metadata["workload"] == "rag_answer_generation"


def test_gateway_backed_generator_requires_execution_context():
    generator = LLMBackedAnswerGenerator(
        gateway=FakeGateway(),
    )

    with pytest.raises(
        ValueError,
        match="execution_context",
    ):
        generator.generate(
            question="Question ?",
            context="[1] Source.",
        )
