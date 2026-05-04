"""Successful responses for MCP server registration and listing."""

from pydantic import Field

from models.api.responses.successful.bases import AbstractSuccessfulResponse
from models.common.mcp import MCPServerAuthInfo, MCPServerInfo


class MCPClientAuthOptionsResponse(AbstractSuccessfulResponse):
    """Response containing MCP servers that accept client-provided authorization.

    Attributes:
        servers: MCP servers that declare client authentication headers.
    """

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


class MCPServerRegistrationResponse(AbstractSuccessfulResponse):
    """Response for a successful MCP server registration.

    Attributes:
        name: Registered MCP server name.
        url: Registered MCP server URL.
        provider_id: MCP provider identification.
        message: Status message.
    """

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
    """Response listing all registered MCP servers.

    Attributes:
        servers: All registered MCP servers (static and dynamic).
    """

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
    """Response for a successful MCP server deletion.

    Attributes:
        name: Deleted MCP server name.
        message: Status message.
    """

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
