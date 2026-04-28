"""Models for query-related REST API requests."""

from typing import Any, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constants import (
    MEDIA_TYPE_JSON,
    MEDIA_TYPE_TEXT,
    SOLR_VECTOR_SEARCH_DEFAULT_MODE,
)
from log import get_logger
from utils import suid

logger = get_logger(__name__)


class Attachment(BaseModel):
    """Model representing an attachment that can be send from the UI as part of query.

    A list of attachments can be an optional part of 'query' request.

    Attributes:
        attachment_type: The attachment type, like "log", "configuration" etc.
        content_type: The content type as defined in MIME standard
        content: The actual attachment content

    YAML attachments with **kind** and **metadata/name** attributes will
    be handled as resources with the specified name:
    ```
    kind: Pod
    metadata:
        name: private-reg
    ```
    """

    attachment_type: str = Field(
        description="The attachment type, like 'log', 'configuration' etc.",
        examples=["log"],
    )
    content_type: str = Field(
        description="The content type as defined in MIME standard",
        examples=["text/plain"],
    )
    content: str = Field(
        description="The actual attachment content",
        examples=["warning: quota exceeded"],
    )

    # provides examples for /docs endpoint
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "attachment_type": "log",
                    "content_type": "text/plain",
                    "content": "this is attachment",
                },
                {
                    "attachment_type": "configuration",
                    "content_type": "application/yaml",
                    "content": "kind: Pod\n metadata:\n name:    private-reg",
                },
                {
                    "attachment_type": "configuration",
                    "content_type": "application/yaml",
                    "content": "foo: bar",
                },
            ]
        },
    }


class SolrVectorSearchRequest(BaseModel):
    """LCORE Solr inline RAG options for ``vector_io.query`` (mode and provider filters).

    Attributes:
        mode: Solr vector_io search mode. When omitted, the server default (hybrid) is used.
        filters: Solr provider filter payload passed through as params['solr'].

    Legacy clients may send a plain JSON object with filter keys only;
    that object is accepted as filters with mode unset (server default applies).
    """

    model_config = ConfigDict(extra="forbid")

    mode: Optional[Literal["semantic", "hybrid", "lexical"]] = Field(
        None,
        description=(
            "Solr vector_io search mode. When omitted, the server default "
            f"({SOLR_VECTOR_SEARCH_DEFAULT_MODE!r}) is used."
        ),
        examples=["hybrid", "semantic", "lexical"],
    )
    filters: Optional[dict[str, Any]] = Field(
        None,
        description="Solr provider filter payload passed through as params['solr'].",
        examples=[{"fq": ["product:*openshift*", "product_version:*4.16*"]}],
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_plain_dict(cls, data: Any) -> Any:
        """Treat a legacy top-level filter dict as filters (backward compatibility).

        Args:
            data: Raw JSON, typically a dict or None.

        Returns:
            Normalized dict for Pydantic model validation, or the original non-dict value.
        """
        if data is None or not isinstance(data, dict):
            return data
        if "filters" in data or "mode" in data:
            return data
        logger.warning(
            "Solr inline RAG: sending filter fields at the top level of `solr` without "
            "`mode` or `filters` is deprecated and will be removed; use "
            '`{"mode": "<semantic|hybrid|lexical>", "filters": {...}}` instead.'
        )
        return {"mode": None, "filters": data}


class QueryRequest(BaseModel):
    """Model representing a request for the LLM (Language Model).

    Attributes:
        query: The query string.
        conversation_id: The optional conversation ID (UUID).
        provider: The optional provider.
        model: The optional model.
        system_prompt: The optional system prompt.
        attachments: The optional attachments.
        no_tools: Whether to bypass all tools and MCP servers (default: False).
        generate_topic_summary: Whether to generate topic summary for new conversations.
        media_type: The optional media type for response format (application/json or text/plain).
        vector_store_ids: The optional list of specific vector store IDs to query for RAG.
        shield_ids: The optional list of safety shield IDs to apply.
        solr: Optional Solr inline RAG options (mode, filters) or legacy filter-only dict.

    Example:
        ```python
        query_request = QueryRequest(query="Tell me about Kubernetes")
        ```
    """

    query: str = Field(
        description="The query string",
        examples=["What is Kubernetes?"],
    )

    conversation_id: Optional[str] = Field(
        None,
        description="The optional conversation ID (UUID)",
        examples=["c5260aec-4d82-4370-9fdf-05cf908b3f16"],
    )

    provider: Optional[str] = Field(
        None,
        description="The optional provider",
        examples=["openai", "watsonx"],
    )

    model: Optional[str] = Field(
        None,
        description="The optional model",
        examples=["gpt4mini"],
    )

    system_prompt: Optional[str] = Field(
        None,
        description="The optional system prompt.",
        examples=["You are OpenShift assistant.", "You are Ansible assistant."],
    )

    attachments: Optional[list[Attachment]] = Field(
        None,
        description="The optional list of attachments.",
        examples=[
            {
                "attachment_type": "log",
                "content_type": "text/plain",
                "content": "this is attachment",
            },
            {
                "attachment_type": "configuration",
                "content_type": "application/yaml",
                "content": "kind: Pod\n metadata:\n name:    private-reg",
            },
            {
                "attachment_type": "configuration",
                "content_type": "application/yaml",
                "content": "foo: bar",
            },
        ],
    )

    no_tools: Optional[bool] = Field(
        False,
        description="Whether to bypass all tools and MCP servers",
        examples=[True, False],
    )

    generate_topic_summary: Optional[bool] = Field(
        True,
        description="Whether to generate topic summary for new conversations",
        examples=[True, False],
    )

    media_type: Optional[str] = Field(
        None,
        description="Media type for the response format",
        examples=[MEDIA_TYPE_JSON, MEDIA_TYPE_TEXT],
    )

    vector_store_ids: Optional[list[str]] = Field(
        None,
        description="Optional list of specific vector store IDs to query for RAG. "
        "If not provided, all available vector stores will be queried.",
        examples=["ocp_docs", "knowledge_base", "vector_db_1"],
    )

    shield_ids: Optional[list[str]] = Field(
        None,
        description="Optional list of safety shield IDs to apply. "
        "If None, all configured shields are used. ",
        examples=["llama-guard", "custom-shield"],
    )

    solr: Optional[SolrVectorSearchRequest] = Field(
        None,
        description=(
            "Solr inline RAG config: mode (semantic, hybrid, lexical) and filters; "
            "a legacy filter-only object (e.g. fq) is still accepted."
        ),
        examples=[
            {"mode": "hybrid", "filters": {"fq": ["product:*openshift*"]}},
            {"filters": {"fq": ["product:*openshift*", "product_version:*4.16*"]}},
        ],
    )

    # provides examples for /docs endpoint
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "query": "write a deployment yaml for the mongodb image",
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                    "provider": "openai",
                    "model": "model-name",
                    "system_prompt": "You are a helpful assistant",
                    "no_tools": False,
                    "generate_topic_summary": True,
                    "vector_store_ids": ["ocp_docs", "knowledge_base"],
                    "attachments": [
                        {
                            "attachment_type": "log",
                            "content_type": "text/plain",
                            "content": "this is attachment",
                        },
                        {
                            "attachment_type": "configuration",
                            "content_type": "application/yaml",
                            "content": "kind: Pod\n metadata:\n    name: private-reg",
                        },
                        {
                            "attachment_type": "configuration",
                            "content_type": "application/yaml",
                            "content": "foo: bar",
                        },
                    ],
                }
            ]
        },
    }

    @field_validator("conversation_id")
    @classmethod
    def check_uuid(cls, value: Optional[str]) -> Optional[str]:
        """
        Validate that a conversation identifier matches the expected SUID format.

        Parameters:
        ----------
            value (Optional[str]): Conversation identifier to validate; may be None.

        Returns:
        -------
            Optional[str]: The original `value` if valid or `None` if not provided.

        Raises:
        ------
            ValueError: If `value` is provided and does not conform to the
                        expected SUID format.
        """
        if value and not suid.check_suid(value):
            raise ValueError(f"Improper conversation ID '{value}'")
        return value

    @model_validator(mode="after")
    def validate_provider_and_model(self) -> Self:
        """
        Ensure `provider` and `model` are specified together.

        Raises:
            ValueError: If only `provider` or only `model` is provided (they must be set together).

        Returns:
            Self: The validated model instance.
        """
        if self.model and not self.provider:
            raise ValueError("Provider must be specified if model is specified")
        if self.provider and not self.model:
            raise ValueError("Model must be specified if provider is specified")
        return self

    @model_validator(mode="after")
    def validate_media_type(self) -> Self:
        """
        Ensure the `media_type`, if present, is one of the allowed response media types.

        Raises:
            ValueError: If `media_type` is not equal to `MEDIA_TYPE_JSON` or `MEDIA_TYPE_TEXT`.

        Returns:
            Self: The model instance when validation passes.
        """
        if self.media_type and self.media_type not in [
            MEDIA_TYPE_JSON,
            MEDIA_TYPE_TEXT,
        ]:
            raise ValueError(
                f"media_type must be either '{MEDIA_TYPE_JSON}' or '{MEDIA_TYPE_TEXT}'"
            )
        return self
