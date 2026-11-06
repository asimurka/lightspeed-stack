"""Tests for PAI run projection into AgentTurnSummary."""

from typing import Optional

from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.usage import RunUsage

from conversations.display_history.agentic.models.turn_items import MessageTurnItem
from conversations.display_history.agentic.projection import project_agent_turn_summary
from models.common.agents import AgentRunDeps
from models.common.turn_summary import ReferencedDocument


def _user_and_assistant(*, finish_reason: str = "stop") -> list:
    return [
        ModelRequest(parts=[UserPromptPart(content="hi")]),
        ModelResponse(
            parts=[TextPart(content="there")],
            finish_reason=finish_reason,  # type: ignore[arg-type]
        ),
    ]


def _completed_run(
    *,
    run_id: str = "resp_1",
    input_tokens: int = 4,
    output_tokens: int = 6,
    messages: Optional[list] = None,
) -> AgentRunResult[str]:
    run = AgentRunResult(output="there")
    run._state.run_id = run_id  # pylint: disable=protected-access
    run._state.usage = RunUsage(  # pylint: disable=protected-access
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    run._state.message_history = (  # pylint: disable=protected-access
        messages if messages is not None else _user_and_assistant()
    )
    return run


def test_project_skips_run_without_id() -> None:
    """A run cancelled before start has no identity to persist."""
    run = RunCancelled("cancelled before start", run_id=None)
    assert project_agent_turn_summary(run, AgentRunDeps()) is None


def test_project_completed_run_to_summary() -> None:
    """Completed PAI runs become persistence fields without envelope identity."""
    summary = project_agent_turn_summary(_completed_run(), AgentRunDeps())
    assert summary is not None
    assert summary.status == "completed"
    assert summary.input_tokens == 4
    assert summary.output_tokens == 6
    assert summary.context_status == "full"
    assert summary.agent is None
    assert isinstance(summary.input[0], MessageTurnItem)
    assert isinstance(summary.output[0], MessageTurnItem)


def test_project_cancelled_run_is_interrupted() -> None:
    """RunCancelled with a run id persists as interrupted."""
    run = RunCancelled(
        "cancelled",
        run_id="resp_cancel",
        messages=_user_and_assistant(),
        usage=RunUsage(input_tokens=1, output_tokens=2),
    )
    summary = project_agent_turn_summary(run, AgentRunDeps())
    assert summary is not None
    assert summary.status == "interrupted"
    assert summary.input_tokens == 1
    assert summary.output_tokens == 2


def test_project_applies_deps() -> None:
    """Capability-collected deps map onto the summary; agent id is not set yet."""
    deps = AgentRunDeps(
        context_status="compacted",
        referenced_documents=[ReferencedDocument(doc_title="OpenShift Docs")],
    )
    summary = project_agent_turn_summary(_completed_run(), deps)
    assert summary is not None
    assert summary.context_status == "compacted"
    assert summary.agent is None
    assert summary.referenced_documents[0].doc_title == "OpenShift Docs"


def test_project_maps_tool_call_finish_to_awaiting_input() -> None:
    """A tool_call finish reason is stored as awaiting_input."""
    summary = project_agent_turn_summary(
        _completed_run(messages=_user_and_assistant(finish_reason="tool_call")),
        AgentRunDeps(),
    )
    assert summary is not None
    assert summary.status == "awaiting_input"
