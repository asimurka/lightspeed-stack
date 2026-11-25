# Responses package

OpenResponses contract models owned by LCORE. Top-level HTTP request and
response envelopes stay in `src/models/api`; structured items, tools, usage,
and SSE events live here.

## [models](models/)

LCORE-owned OpenResponses item, tool, config, envelope, and stream-event types.

## [projector](projector/)

`OpenResponsesEventStream` maps Pydantic AI `run_stream_events` output onto
those events. It does not build or run the agent. SSE (`encode_event`) and
buffered JSON (`final_response` / `consume`) share the same stream.
