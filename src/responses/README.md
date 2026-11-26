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

Callers always pass the native PAI iterator to `transform_stream`. Shield
capabilities skip the main model via `wrap_model_request` / `SkipModelRequest`
and PAI replays `PartStartEvent` plus `PartEndEvent` (full text on start, no
token deltas). The projector treats those parts like any other assistant
message.
