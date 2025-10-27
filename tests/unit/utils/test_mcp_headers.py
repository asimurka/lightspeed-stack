"""Unit tests for MCP headers utility functions."""

import pytest
from fastapi import Request
from pytest_mock import MockerFixture

from utils import mcp_headers


def test_extract_mcp_headers_empty_headers(mocker: MockerFixture) -> None:
    """Test the extract_mcp_headers function for request without any headers."""
    request = mocker.Mock(spec=Request)
    # no headers
    request.headers = {}

    result = mcp_headers.extract_mcp_headers(request)
    assert result == {}


def test_extract_mcp_headers_mcp_headers_empty(mocker: MockerFixture) -> None:
    """Test the extract_mcp_headers function for request with empty MCP-HEADERS header."""
    request = mocker.Mock(spec=Request)
    # empty MCP-HEADERS
    request.headers = {"MCP-HEADERS": ""}

    # empty dict should be returned
    result = mcp_headers.extract_mcp_headers(request)
    assert result == {}


def test_extract_mcp_headers_valid_mcp_header(mocker: MockerFixture) -> None:
    """Test the extract_mcp_headers function for request with valid MCP-HEADERS header."""
    request = mocker.Mock(spec=Request)
    # valid MCP-HEADERS
    request.headers = {"MCP-HEADERS": '{"http://www.redhat.com": {"auth": "token123"}}'}

    result = mcp_headers.extract_mcp_headers(request)

    expected = {"http://www.redhat.com": {"auth": "token123"}}
    assert result == expected


def test_extract_mcp_headers_valid_mcp_headers(mocker: MockerFixture) -> None:
    """Test the extract_mcp_headers function for request with valid MCP-HEADERS headers."""
    request = mocker.Mock(spec=Request)
    # valid MCP-HEADERS
    header1 = '"http://www.redhat.com": {"auth": "token123"}'
    header2 = '"http://www.example.com": {"auth": "tokenXYZ"}'

    request.headers = {"MCP-HEADERS": f"{{{header1}, {header2}}}"}

    result = mcp_headers.extract_mcp_headers(request)

    expected = {
        "http://www.redhat.com": {"auth": "token123"},
        "http://www.example.com": {"auth": "tokenXYZ"},
    }
    assert result == expected


def test_extract_mcp_headers_invalid_json_mcp_header(mocker: MockerFixture) -> None:
    """Test the extract_mcp_headers function for request with invalid MCP-HEADERS header."""
    request = mocker.Mock(spec=Request)
    # invalid MCP-HEADERS - not a JSON
    request.headers = {"MCP-HEADERS": "this-is-invalid"}

    # empty dict should be returned
    result = mcp_headers.extract_mcp_headers(request)
    assert result == {}


def test_extract_mcp_headers_invalid_mcp_header_type(mocker: MockerFixture) -> None:
    """Test the extract_mcp_headers function for request with invalid MCP-HEADERS header type."""
    request = mocker.Mock(spec=Request)
    # invalid MCP-HEADERS - not a dict
    request.headers = {"MCP-HEADERS": "[]"}

    # empty dict should be returned
    result = mcp_headers.extract_mcp_headers(request)
    assert result == {}


def test_extract_mcp_headers_invalid_mcp_header_null_value(
    mocker: MockerFixture,
) -> None:
    """Test the extract_mcp_headers function for request with invalid MCP-HEADERS header type."""
    request = mocker.Mock(spec=Request)
    # invalid MCP-HEADERS - not a dict
    request.headers = {"MCP-HEADERS": "null"}

    # empty dict should be returned
    result = mcp_headers.extract_mcp_headers(request)
    assert result == {}


@pytest.mark.asyncio
async def test_mcp_headers_dependency_empty_headers(mocker: MockerFixture) -> None:
    """Test the mcp_headers_dependency function for request with empty MCP-HEADERS header."""
    request = mocker.Mock(spec=Request)
    # empty MCP-HEADERS
    request.headers = {"MCP-HEADERS": ""}

    # empty dict should be returned
    result = await mcp_headers.mcp_headers_dependency(request)
    assert result == {}


@pytest.mark.asyncio
async def test_mcp_headers_dependency_mcp_headers_empty(mocker: MockerFixture) -> None:
    """Test the mcp_headers_dependency function for request with empty MCP-HEADERS header."""
    request = mocker.Mock(spec=Request)
    # empty MCP-HEADERS
    request.headers = {"MCP-HEADERS": ""}

    # empty dict should be returned
    result = await mcp_headers.mcp_headers_dependency(request)
    assert result == {}


@pytest.mark.asyncio
async def test_mcp_headers_dependency_valid_mcp_header(mocker: MockerFixture) -> None:
    """Test the mcp_headers_dependency function for request with valid MCP-HEADERS header."""
    request = mocker.Mock(spec=Request)
    # valid MCP-HEADERS
    request.headers = {"MCP-HEADERS": '{"http://www.redhat.com": {"auth": "token123"}}'}

    result = await mcp_headers.mcp_headers_dependency(request)

    expected = {"http://www.redhat.com": {"auth": "token123"}}
    assert result == expected


@pytest.mark.asyncio
async def test_mcp_headers_dependency_valid_mcp_headers(mocker: MockerFixture) -> None:
    """Test the mcp_headers_dependency function for request with valid MCP-HEADERS headers."""
    request = mocker.Mock(spec=Request)
    # valid MCP-HEADERS
    header1 = '"http://www.redhat.com": {"auth": "token123"}'
    header2 = '"http://www.example.com": {"auth": "tokenXYZ"}'

    request.headers = {"MCP-HEADERS": f"{{{header1}, {header2}}}"}

    result = await mcp_headers.mcp_headers_dependency(request)

    expected = {
        "http://www.redhat.com": {"auth": "token123"},
        "http://www.example.com": {"auth": "tokenXYZ"},
    }
    assert result == expected


@pytest.mark.asyncio
async def test_mcp_headers_dependency_invalid_json_mcp_header(
    mocker: MockerFixture,
) -> None:
    """Test the mcp_headers_dependency function for request with invalid MCP-HEADERS header."""
    request = mocker.Mock(spec=Request)
    # invalid MCP-HEADERS - not a JSON
    request.headers = {"MCP-HEADERS": "this-is-invalid"}

    # empty dict should be returned
    result = await mcp_headers.mcp_headers_dependency(request)
    assert result == {}


@pytest.mark.asyncio
async def test_mcp_headers_dependency_invalid_mcp_header_type(
    mocker: MockerFixture,
) -> None:
    """Test the mcp_headers_dependency function for request with invalid MCP-HEADERS header type."""
    request = mocker.Mock(spec=Request)
    # invalid MCP-HEADERS - not a dict
    request.headers = {"MCP-HEADERS": "[]"}

    # empty dict should be returned
    result = await mcp_headers.mcp_headers_dependency(request)
    assert result == {}


@pytest.mark.asyncio
async def test_mcp_headers_dependency_invalid_mcp_header_null_value(
    mocker: MockerFixture,
) -> None:
    """Test the mcp_headers_dependency function for request with invalid MCP-HEADERS header type."""
    request = mocker.Mock(spec=Request)
    # invalid MCP-HEADERS - not a dict
    request.headers = {"MCP-HEADERS": "null"}

    # empty dict should be returned
    result = await mcp_headers.mcp_headers_dependency(request)
    assert result == {}
