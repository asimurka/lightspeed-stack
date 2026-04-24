# pylint: disable=redefined-outer-name, too-many-locals, too-few-public-methods
"""Unit tests for Splunk telemetry in the /responses endpoint."""

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from llama_stack_api import OpenAIResponseObject
from llama_stack_api.openai_responses import OpenAIResponseMessage
from llama_stack_client import APIConnectionError, AsyncLlamaStackClient
from llama_stack_client import APIStatusError as LLSApiStatusError
from openai._exceptions import APIStatusError as OpenAIAPIStatusError
from pytest_mock import MockerFixture

from app.endpoints.responses import (
    _background_splunk_tasks,
    _queue_responses_splunk_event,
    handle_non_streaming_response,
    handle_streaming_response,
)
from configuration import AppConfig
from models.requests import ResponsesRequest
from observability.formats.responses import ResponsesEventData
from utils.types import (
    RAGContext,
    ResponsesApiParams,
    ResponsesContext,
    ShieldModerationBlocked,
    ShieldModerationPassed,
    TurnSummary,
)

MODULE = "app.endpoints.responses"
MOCK_AUTH = (
    "00000001-0001-0001-0001-000000000001",
    "mock_username",
    False,
    "mock_token",
)
VALID_CONV_ID = "conv_e6afd7aaa97b49ce8f4f96a801b07893d9cb784d72e53e3c"
VALID_CONV_ID_NORMALIZED = "e6afd7aaa97b49ce8f4f96a801b07893d9cb784d72e53e3c"


def _api_params_from_request(request: ResponsesRequest) -> ResponsesApiParams:
    """Build ``ResponsesApiParams`` the same way the endpoint does."""
    return ResponsesApiParams.model_validate(request.model_dump())


def _telemetry_context(
    mock_client: Any,
    *,
    input_text: str,
    started_at: datetime,
    moderation_result: ShieldModerationPassed | ShieldModerationBlocked,
    inline_rag_context: RAGContext | None = None,
    background_tasks: Optional[BackgroundTasks] = None,
    rh_identity_context: tuple[str, str] = ("", ""),
) -> ResponsesContext:
    """Build ``ResponsesContext`` for handler / Splunk tests."""
    return ResponsesContext(
        client=mock_client,
        auth=MOCK_AUTH,
        input_text=input_text,
        started_at=started_at,
        moderation_result=moderation_result,
        inline_rag_context=inline_rag_context or RAGContext(),
        background_tasks=background_tasks,
        rh_identity_context=rh_identity_context,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request_with_model_and_conv(
    input_text: str = "Hello", model: str = "provider/model1"
) -> ResponsesRequest:
    """Build request with model and conversation set (as handler does)."""
    return ResponsesRequest(
        input=input_text,
        model=model,
        conversation=VALID_CONV_ID,
    )


def _patch_handle_non_streaming_common(
    mocker: MockerFixture, config: AppConfig
) -> None:
    """Patch deps used by handle_non_streaming_response (blocked and success)."""
    mocker.patch(f"{MODULE}.configuration", config)
    mocker.patch(f"{MODULE}.get_available_quotas", return_value={})
    mocker.patch(
        f"{MODULE}.get_topic_summary",
        new=mocker.AsyncMock(return_value=None),
    )
    mocker.patch(f"{MODULE}.store_query_results")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="splunk_background_tasks")
def splunk_background_tasks_fixture() -> BackgroundTasks:
    """Real ``BackgroundTasks`` so ``ResponsesContext`` validates like production."""
    return BackgroundTasks()


@pytest.fixture(name="minimal_config")
def minimal_config_fixture() -> AppConfig:
    """Minimal AppConfig for responses endpoint tests."""
    cfg = AppConfig()
    cfg.init_from_dict(
        {
            "name": "test",
            "service": {"host": "localhost", "port": 8080},
            "llama_stack": {
                "api_key": "test-key",
                "url": "http://test.com:1234",
                "use_as_library_client": False,
            },
            "user_data_collection": {},
            "authentication": {"module": "noop"},
            "authorization": {"access_rules": []},
        }
    )
    return cfg


# ---------------------------------------------------------------------------
# Test 1: _queue_responses_splunk_event unit test
# ---------------------------------------------------------------------------


class TestQueueResponsesSplunkEvent:
    """Unit tests for the _queue_responses_splunk_event helper."""

    def test_noop_when_background_tasks_is_none(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verify no-op when background_tasks is None (Splunk disabled)."""
        mock_build = mocker.patch(f"{MODULE}.build_responses_event")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)
        request = ResponsesRequest(
            input="user question",
            model="provider/model1",
            conversation=VALID_CONV_ID,
        )
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="user question",
            started_at=datetime.now(UTC),
            moderation_result=ShieldModerationPassed(),
            background_tasks=None,
            rh_identity_context=("org1", "sys1"),
        )

        _queue_responses_splunk_event(
            response_text="llm answer",
            sourcetype="responses_completed",
            api_params=api_params,
            context=context,
        )

        mock_build.assert_not_called()

    def test_builds_event_and_queues_background_task(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verify event is built from ResponsesEventData and queued via add_task."""
        mock_build = mocker.patch(
            f"{MODULE}.build_responses_event", return_value={"built": True}
        )
        mock_send = mocker.patch(f"{MODULE}.send_splunk_event")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)
        background_tasks = BackgroundTasks()
        add_task_spy = mocker.spy(background_tasks, "add_task")
        started_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        fake_datetime = mocker.MagicMock()
        fake_datetime.UTC = UTC
        fake_datetime.now.return_value = started_at + timedelta(seconds=1.23)
        mocker.patch(f"{MODULE}.datetime", fake_datetime)
        request = ResponsesRequest(
            input="user question",
            model="provider/model1",
            conversation=VALID_CONV_ID,
        )
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="user question",
            started_at=started_at,
            moderation_result=ShieldModerationPassed(),
            background_tasks=background_tasks,
            rh_identity_context=("org1", "sys1"),
        )

        _queue_responses_splunk_event(
            response_text="llm answer",
            sourcetype="responses_completed",
            api_params=api_params,
            context=context,
            input_tokens=100,
            output_tokens=50,
        )

        mock_build.assert_called_once()
        event_data = mock_build.call_args[0][0]
        assert isinstance(event_data, ResponsesEventData)
        assert event_data.input_text == "user question"
        assert event_data.response_text == "llm answer"
        assert event_data.conversation_id == VALID_CONV_ID_NORMALIZED
        assert event_data.model == "provider/model1"
        assert event_data.org_id == "org1"
        assert event_data.system_id == "sys1"
        assert event_data.inference_time == 1.23
        assert event_data.input_tokens == 100
        assert event_data.output_tokens == 50

        add_task_spy.assert_called_once_with(
            mock_send, {"built": True}, "responses_completed"
        )

    def test_fire_and_forget_dispatches_via_create_task(
        self,
        mocker: MockerFixture,
    ) -> None:
        """fire_and_forget=True dispatches via asyncio.create_task with GC protection."""
        mocker.patch(f"{MODULE}.build_responses_event", return_value={"built": True})
        # Use MagicMock (not AsyncMock) so send_splunk_event() returns a
        # comparable return_value instead of a coroutine object.
        mock_send = mocker.patch(f"{MODULE}.send_splunk_event", new=mocker.MagicMock())
        mock_task = mocker.MagicMock()
        mock_create_task = mocker.patch("asyncio.create_task", return_value=mock_task)

        # Clear any leftover tasks from other tests
        _background_splunk_tasks.clear()

        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)
        request = ResponsesRequest(
            input="user question",
            model="provider/model1",
            conversation=VALID_CONV_ID,
        )
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="user question",
            started_at=datetime.now(UTC),
            moderation_result=ShieldModerationPassed(),
            background_tasks=None,
            rh_identity_context=("org1", "sys1"),
        )

        _queue_responses_splunk_event(
            response_text="error message",
            sourcetype="responses_error",
            api_params=api_params,
            context=context,
            fire_and_forget=True,
        )

        mock_send.assert_called_once_with({"built": True}, "responses_error")
        mock_create_task.assert_called_once_with(mock_send.return_value)

        # Task is held in the module-level set to prevent GC
        assert mock_task in _background_splunk_tasks
        # done_callback registered to clean up after completion
        mock_task.add_done_callback.assert_called_once()

        # Simulate task completion: callback removes from set
        done_callback = mock_task.add_done_callback.call_args[0][0]
        done_callback(mock_task)
        assert mock_task not in _background_splunk_tasks


# ---------------------------------------------------------------------------
# Tests 2-8: Integration tests for telemetry hook paths
# ---------------------------------------------------------------------------


class TestSplunkTelemetryHooks:
    """Integration tests verifying _queue_responses_splunk_event is called at each hook."""

    # -- Non-streaming paths ------------------------------------------------

    @pytest.mark.asyncio
    async def test_non_streaming_shield_blocked(
        self,
        minimal_config: AppConfig,
        splunk_background_tasks: BackgroundTasks,
        mocker: MockerFixture,
    ) -> None:
        """Blocked moderation fires responses_shield_blocked telemetry."""
        request = _request_with_model_and_conv("Bad input")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)

        mock_refusal = OpenAIResponseMessage(
            role="assistant", content="Content blocked", type="message"
        )
        moderation = ShieldModerationBlocked(
            message="Content blocked",
            moderation_id="mod_blocked_1",
            refusal_response=mock_refusal,
        )

        _patch_handle_non_streaming_common(mocker, minimal_config)
        mock_client.conversations.items.create = mocker.AsyncMock()
        mock_api_response = mocker.Mock()
        mock_api_response.output = [mock_refusal]
        mock_api_response.model_dump.return_value = {
            "id": "resp_blocked",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "model": "provider/model1",
            "output": [],
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }
        mocker.patch(
            f"{MODULE}.OpenAIResponseObject.model_construct",
            return_value=mock_api_response,
        )
        mock_queue = mocker.patch(f"{MODULE}._queue_responses_splunk_event")

        started_at = datetime.now(UTC)
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="Bad input",
            started_at=started_at,
            moderation_result=moderation,
            background_tasks=splunk_background_tasks,
            rh_identity_context=("org1", "sys1"),
        )
        await handle_non_streaming_response(
            original_request=request,
            api_params=api_params,
            context=context,
        )

        mock_queue.assert_called_once()
        call_kwargs = mock_queue.call_args[1]
        assert call_kwargs["sourcetype"] == "responses_shield_blocked"
        assert call_kwargs["context"].background_tasks is splunk_background_tasks
        assert call_kwargs["context"].rh_identity_context == ("org1", "sys1")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc_factory",
        [
            pytest.param(
                lambda m: APIConnectionError(request=m.Mock()),
                id="APIConnectionError",
            ),
            pytest.param(
                lambda m: RuntimeError("context_length exceeded"),
                id="RuntimeError-context-length",
            ),
            pytest.param(
                lambda m: LLSApiStatusError(
                    message="API error", response=m.Mock(request=None), body=None
                ),
                id="LLSApiStatusError",
            ),
            pytest.param(
                lambda m: OpenAIAPIStatusError(
                    message="API error", response=m.Mock(request=None), body=None
                ),
                id="OpenAIAPIStatusError",
            ),
        ],
    )
    async def test_non_streaming_error_fires_telemetry(
        self,
        exc_factory: Any,
        minimal_config: AppConfig,
        splunk_background_tasks: BackgroundTasks,
        mocker: MockerFixture,
    ) -> None:
        """Each error branch fires responses_error telemetry with fire_and_forget."""
        request = _request_with_model_and_conv("Hello")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)
        moderation = ShieldModerationPassed()

        mock_client.responses.create = mocker.AsyncMock(side_effect=exc_factory(mocker))

        _patch_handle_non_streaming_common(mocker, minimal_config)
        mocker.patch(
            f"{MODULE}.normalize_conversation_id",
            return_value=VALID_CONV_ID_NORMALIZED,
        )
        mocker.patch(
            f"{MODULE}.handle_known_apistatus_errors",
            return_value=mocker.Mock(
                model_dump=lambda: {
                    "status_code": 500,
                    "detail": {"response": "Error", "cause": "API error"},
                }
            ),
        )
        mock_queue = mocker.patch(f"{MODULE}._queue_responses_splunk_event")

        started_at = datetime.now(UTC)
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="Hello",
            started_at=started_at,
            moderation_result=moderation,
            background_tasks=splunk_background_tasks,
            rh_identity_context=("org1", "sys1"),
        )
        with pytest.raises(HTTPException):
            await handle_non_streaming_response(
                original_request=request,
                api_params=api_params,
                context=context,
            )

        mock_queue.assert_called_once()
        assert mock_queue.call_args[1]["sourcetype"] == "responses_error"
        assert mock_queue.call_args[1]["fire_and_forget"] is True

    @pytest.mark.asyncio
    async def test_non_streaming_success(
        self,
        minimal_config: AppConfig,
        splunk_background_tasks: BackgroundTasks,
        mocker: MockerFixture,
    ) -> None:
        """Successful non-streaming response fires responses_completed with token counts."""
        request = _request_with_model_and_conv("Hello")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)
        moderation = ShieldModerationPassed()

        mock_api_response = mocker.Mock(spec=OpenAIResponseObject)
        mock_api_response.output = []
        mock_api_response.usage = mocker.Mock(
            input_tokens=100, output_tokens=50, total_tokens=150
        )
        mock_api_response.model_dump.return_value = {
            "id": "resp_1",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "model": "provider/model1",
            "output": [],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }
        mock_client.responses.create = mocker.AsyncMock(return_value=mock_api_response)

        _patch_handle_non_streaming_common(mocker, minimal_config)
        mocker.patch(
            f"{MODULE}.extract_token_usage",
            return_value=mocker.Mock(input_tokens=100, output_tokens=50),
        )
        mocker.patch(f"{MODULE}.consume_query_tokens")
        mocker.patch(
            f"{MODULE}.extract_text_from_response_items",
            return_value="Model reply",
        )
        mocker.patch(f"{MODULE}.extract_vector_store_ids_from_tools", return_value=[])
        mocker.patch(
            f"{MODULE}.normalize_conversation_id",
            return_value=VALID_CONV_ID_NORMALIZED,
        )
        mock_turn_summary = mocker.Mock()
        mock_turn_summary.referenced_documents = []
        mock_turn_summary.rag_chunks = []
        mock_token_usage = mocker.Mock()
        mock_token_usage.input_tokens = 100
        mock_token_usage.output_tokens = 50
        mock_turn_summary.token_usage = mock_token_usage
        mocker.patch(f"{MODULE}.build_turn_summary", return_value=mock_turn_summary)
        mocker.patch(f"{MODULE}.deduplicate_referenced_documents", return_value=[])

        mock_queue = mocker.patch(f"{MODULE}._queue_responses_splunk_event")

        started_at = datetime.now(UTC)
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="Hello",
            started_at=started_at,
            moderation_result=moderation,
            background_tasks=splunk_background_tasks,
            rh_identity_context=("org1", "sys1"),
        )
        await handle_non_streaming_response(
            original_request=request,
            api_params=api_params,
            context=context,
        )

        # The success hook fires once (blocked hook is skipped because decision != "blocked")
        mock_queue.assert_called_once()
        call_kwargs = mock_queue.call_args[1]
        assert call_kwargs["sourcetype"] == "responses_completed"
        assert call_kwargs["input_tokens"] == 100
        assert call_kwargs["output_tokens"] == 50

    # -- Streaming paths ----------------------------------------------------

    @pytest.mark.asyncio
    async def test_streaming_shield_blocked(
        self,
        minimal_config: AppConfig,
        splunk_background_tasks: BackgroundTasks,
        mocker: MockerFixture,
    ) -> None:
        """Blocked moderation in streaming fires responses_shield_blocked telemetry."""
        request = _request_with_model_and_conv("Bad", model="provider/model1")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)

        mock_refusal = OpenAIResponseMessage(
            role="assistant", content="Blocked", type="message"
        )
        moderation = ShieldModerationBlocked(
            message="Blocked",
            moderation_id="mod_123",
            refusal_response=mock_refusal,
        )

        mocker.patch(f"{MODULE}.configuration", minimal_config)
        mocker.patch(f"{MODULE}.get_available_quotas", return_value={})
        mocker.patch(
            f"{MODULE}.normalize_conversation_id",
            return_value=VALID_CONV_ID_NORMALIZED,
        )
        mocker.patch(
            f"{MODULE}.get_topic_summary",
            new=mocker.AsyncMock(return_value=None),
        )
        mocker.patch(f"{MODULE}.store_query_results")
        mock_client.conversations.items.create = mocker.AsyncMock()

        mock_queue = mocker.patch(f"{MODULE}._queue_responses_splunk_event")

        started_at = datetime.now(UTC)
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="Bad",
            started_at=started_at,
            moderation_result=moderation,
            background_tasks=splunk_background_tasks,
            rh_identity_context=("org1", "sys1"),
        )
        response = await handle_streaming_response(
            original_request=request,
            api_params=api_params,
            context=context,
        )

        assert isinstance(response, StreamingResponse)
        # Consume the stream to trigger generate_response() completion
        async for _chunk in response.body_iterator:
            pass
        mock_queue.assert_called_once()
        assert mock_queue.call_args[1]["sourcetype"] == "responses_shield_blocked"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc_factory",
        [
            pytest.param(
                lambda m: APIConnectionError(request=m.Mock()),
                id="APIConnectionError",
            ),
            pytest.param(
                lambda m: RuntimeError("context_length exceeded"),
                id="RuntimeError-context-length",
            ),
            pytest.param(
                lambda m: LLSApiStatusError(
                    message="API error", response=m.Mock(request=None), body=None
                ),
                id="LLSApiStatusError",
            ),
            pytest.param(
                lambda m: OpenAIAPIStatusError(
                    message="API error", response=m.Mock(request=None), body=None
                ),
                id="OpenAIAPIStatusError",
            ),
        ],
    )
    async def test_streaming_error_fires_telemetry(
        self,
        exc_factory: Any,
        minimal_config: AppConfig,
        splunk_background_tasks: BackgroundTasks,
        mocker: MockerFixture,
    ) -> None:
        """Each streaming error branch fires responses_error telemetry with fire_and_forget."""
        request = _request_with_model_and_conv("Hello")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)
        moderation = ShieldModerationPassed()

        mock_client.responses.create = mocker.AsyncMock(side_effect=exc_factory(mocker))

        mocker.patch(f"{MODULE}.configuration", minimal_config)
        mocker.patch(
            f"{MODULE}.normalize_conversation_id",
            return_value=VALID_CONV_ID_NORMALIZED,
        )
        mocker.patch(
            f"{MODULE}.handle_known_apistatus_errors",
            return_value=mocker.Mock(
                model_dump=lambda: {
                    "status_code": 500,
                    "detail": {"response": "Error", "cause": "API error"},
                }
            ),
        )
        mock_queue = mocker.patch(f"{MODULE}._queue_responses_splunk_event")

        started_at = datetime.now(UTC)
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="Hello",
            started_at=started_at,
            moderation_result=moderation,
            background_tasks=splunk_background_tasks,
            rh_identity_context=("org1", "sys1"),
        )
        with pytest.raises(HTTPException):
            await handle_streaming_response(
                original_request=request,
                api_params=api_params,
                context=context,
            )

        mock_queue.assert_called_once()
        assert mock_queue.call_args[1]["sourcetype"] == "responses_error"
        assert mock_queue.call_args[1]["fire_and_forget"] is True

    @pytest.mark.asyncio
    async def test_streaming_success(
        self,
        minimal_config: AppConfig,
        splunk_background_tasks: BackgroundTasks,
        mocker: MockerFixture,
    ) -> None:
        """Successful streaming fires responses_completed after consuming the stream."""
        request = _request_with_model_and_conv("Hi", model="provider/model1")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)
        moderation = ShieldModerationPassed()

        mock_chunk = mocker.Mock()
        mock_chunk.type = "response.completed"
        mock_chunk.response = mocker.Mock()
        mock_chunk.response.id = "r1"
        mock_chunk.response.output = []
        mock_chunk.response.usage = mocker.Mock(
            input_tokens=100, output_tokens=50, total_tokens=150
        )
        mock_chunk.model_dump.return_value = {
            "type": "response.completed",
            "response": {
                "id": "r1",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        }

        async def mock_stream() -> Any:
            """Yield a single completed chunk."""
            yield mock_chunk

        mock_client.responses.create = mocker.AsyncMock(return_value=mock_stream())

        mocker.patch(f"{MODULE}.configuration", minimal_config)
        mocker.patch(f"{MODULE}.get_available_quotas", return_value={})
        mocker.patch(
            f"{MODULE}.extract_token_usage",
            return_value=mocker.Mock(input_tokens=100, output_tokens=50),
        )
        mocker.patch(f"{MODULE}.consume_query_tokens")
        mocker.patch(f"{MODULE}.extract_vector_store_ids_from_tools", return_value=[])
        mock_turn_summary = TurnSummary(referenced_documents=[])
        mock_token_usage = mocker.Mock()
        mock_token_usage.input_tokens = 100
        mock_token_usage.output_tokens = 50
        mock_turn_summary.token_usage = mock_token_usage
        mocker.patch(f"{MODULE}.build_turn_summary", return_value=mock_turn_summary)
        mocker.patch(
            f"{MODULE}.get_topic_summary",
            new=mocker.AsyncMock(return_value=None),
        )
        mocker.patch(f"{MODULE}.store_query_results")
        mocker.patch(
            f"{MODULE}.normalize_conversation_id",
            return_value=VALID_CONV_ID_NORMALIZED,
        )
        mock_holder = mocker.Mock()
        mock_holder.get_client.return_value = mock_client
        mocker.patch(f"{MODULE}.AsyncLlamaStackClientHolder", return_value=mock_holder)

        mock_queue = mocker.patch(f"{MODULE}._queue_responses_splunk_event")

        started_at = datetime.now(UTC)
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="Hi",
            started_at=started_at,
            moderation_result=moderation,
            background_tasks=splunk_background_tasks,
            rh_identity_context=("org1", "sys1"),
        )
        response = await handle_streaming_response(
            original_request=request,
            api_params=api_params,
            context=context,
        )

        assert isinstance(response, StreamingResponse)

        # Consume the stream to trigger generate_response() to run to completion
        async for _chunk in response.body_iterator:
            pass  # drain the generator so post-stream hooks fire

        mock_queue.assert_called_once()
        call_kwargs = mock_queue.call_args[1]
        assert call_kwargs["sourcetype"] == "responses_completed"
        assert call_kwargs["input_tokens"] == 100
        assert call_kwargs["output_tokens"] == 50

    # -- Splunk disabled (no BackgroundTasks) --------------------------------

    @pytest.mark.asyncio
    async def test_splunk_disabled_no_background_tasks(
        self,
        minimal_config: AppConfig,
        mocker: MockerFixture,
    ) -> None:
        """When background_tasks is None, _queue_responses_splunk_event is never called."""
        request = _request_with_model_and_conv("Bad input")
        mock_client = mocker.AsyncMock(spec=AsyncLlamaStackClient)

        mock_refusal = OpenAIResponseMessage(
            role="assistant", content="Content blocked", type="message"
        )
        moderation = ShieldModerationBlocked(
            message="Content blocked",
            moderation_id="mod_disabled",
            refusal_response=mock_refusal,
        )

        _patch_handle_non_streaming_common(mocker, minimal_config)
        mock_client.conversations.items.create = mocker.AsyncMock()
        mock_api_response = mocker.Mock()
        mock_api_response.output = [mock_refusal]
        mock_api_response.model_dump.return_value = {
            "id": "resp_disabled",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "model": "provider/model1",
            "output": [],
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }
        mocker.patch(
            f"{MODULE}.OpenAIResponseObject.model_construct",
            return_value=mock_api_response,
        )
        mock_queue = mocker.patch(f"{MODULE}._queue_responses_splunk_event")

        # background_tasks=None (the default) means Splunk is disabled
        started_at = datetime.now(UTC)
        api_params = _api_params_from_request(request)
        context = _telemetry_context(
            mock_client,
            input_text="Bad input",
            started_at=started_at,
            moderation_result=moderation,
            background_tasks=None,
            rh_identity_context=("org1", "sys1"),
        )
        await handle_non_streaming_response(
            original_request=request,
            api_params=api_params,
            context=context,
        )

        mock_queue.assert_called_once()
        assert mock_queue.call_args[1]["context"].background_tasks is None
