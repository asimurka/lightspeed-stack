# pylint: disable=too-many-lines

"""Models for REST API responses."""

from pydantic import BaseModel, Field

from models.api.responses.successful.bases import AbstractSuccessfulResponse


class MCPServerAuthInfo(BaseModel):
    """Information about MCP server client authentication options."""

    name: str = Field(..., description="MCP server name")
    client_auth_headers: list[str] = Field(
        ...,
        description="List of authentication header names for client-provided tokens",
    )


class MCPClientAuthOptionsResponse(AbstractSuccessfulResponse):
    """Response containing MCP servers that accept client-provided authorization."""

    servers: list[MCPServerAuthInfo] = Field(
        default_factory=list,
        description="List of MCP servers that accept client-provided authorization",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "servers": [
                        {
                            "name": "github",
                            "client_auth_headers": ["Authorization"],
                        },
                        {
                            "name": "gitlab",
                            "client_auth_headers": ["Authorization", "X-API-Key"],
                        },
                    ]
                }
            ]
        }
    }


class MCPServerInfo(BaseModel):
    """Information about a registered MCP server.

    Attributes:
        name: Unique name of the MCP server.
        url: URL of the MCP server endpoint.
        provider_id: MCP provider identification.
        source: Whether the server was registered statically (config) or dynamically (api).
    """

    name: str = Field(..., description="MCP server name")
    url: str = Field(..., description="MCP server URL")
    provider_id: str = Field(..., description="MCP provider identification")
    source: str = Field(
        ...,
        description="How the server was registered: 'config' (static) or 'api' (dynamic)",
        examples=["config", "api"],
    )


class MCPServerRegistrationResponse(AbstractSuccessfulResponse):
    """Response for a successful MCP server registration."""

    name: str = Field(..., description="Registered MCP server name")
    url: str = Field(..., description="Registered MCP server URL")
    provider_id: str = Field(..., description="MCP provider identification")
    message: str = Field(..., description="Status message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "mcp-integration-tools",
                    "url": "http://host.docker.internal:7008/api/mcp-actions/v1",
                    "provider_id": "model-context-protocol",
                    "message": "MCP server 'mcp-integration-tools' registered successfully",
                }
            ]
        }
    }


class MCPServerListResponse(AbstractSuccessfulResponse):
    """Response listing all registered MCP servers."""

    servers: list[MCPServerInfo] = Field(
        default_factory=list,
        description="List of all registered MCP servers (static and dynamic)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "servers": [
                        {
                            "name": "mcp-integration-tools",
                            "url": "http://host.docker.internal:7008/api/mcp-actions/v1",
                            "provider_id": "model-context-protocol",
                            "source": "config",
                        },
                        {
                            "name": "test-mcp-server",
                            "url": "http://host.docker.internal:8888/mcp",
                            "provider_id": "model-context-protocol",
                            "source": "api",
                        },
                    ]
                }
            ]
        }
    }


class MCPServerDeleteResponse(AbstractSuccessfulResponse):
    """Response for a successful MCP server deletion."""

    name: str = Field(..., description="Deleted MCP server name")
    message: str = Field(..., description="Status message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "test-mcp-server",
                    "message": "MCP server 'test-mcp-server' unregistered successfully",
                }
            ]
        }
    }
