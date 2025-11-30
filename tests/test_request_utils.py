"""Tests for the request utilities module."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from starlette.requests import Request

from yak_shears._yak.request_utils import extract_yak_path, is_htmx_request


def _mock_request(
    method: str = "GET",
    headers_get_return: str | None = None,
    query_params_get_return: str | None = None,
) -> MagicMock:
    """Create a mock request with proper property mocking."""
    request = MagicMock(spec=Request)
    type(request).method = PropertyMock(return_value=method)

    # Mock headers.get() method
    headers_mock = MagicMock()
    headers_mock.get = MagicMock(return_value=headers_get_return)
    type(request).headers = PropertyMock(return_value=headers_mock)

    # Mock query_params.get() method
    query_params_mock = MagicMock()
    query_params_mock.get = MagicMock(return_value=query_params_get_return)
    type(request).query_params = PropertyMock(return_value=query_params_mock)

    return request


class TestIsHtmxRequest:
    def test_htmx_request_true(self) -> None:
        request = _mock_request(headers_get_return="true")
        assert is_htmx_request(request) is True

    def test_htmx_request_false(self) -> None:
        request = _mock_request(headers_get_return=None)
        assert is_htmx_request(request) is False

    def test_htmx_request_other_value(self) -> None:
        request = _mock_request(headers_get_return="false")
        assert is_htmx_request(request) is False


class TestExtractYakPath:
    @pytest.mark.asyncio
    async def test_extract_from_htmx_form(self) -> None:
        request = _mock_request(method="POST", headers_get_return="true")

        form_data = MagicMock()
        form_data.get.return_value = "category/file.dj"
        request.form = AsyncMock(return_value=form_data)

        result = await extract_yak_path(request)
        assert result == "category/file.dj"

    @pytest.mark.asyncio
    async def test_extract_from_post_form(self) -> None:
        request = _mock_request(method="POST", headers_get_return=None, query_params_get_return="")

        form_data = MagicMock()
        form_data.get.return_value = "category/file.dj"
        request.form = AsyncMock(return_value=form_data)

        result = await extract_yak_path(request)
        assert result == "category/file.dj"

    @pytest.mark.asyncio
    async def test_extract_prefers_query_params_over_form(self) -> None:
        request = _mock_request(method="POST", headers_get_return=None, query_params_get_return="from_query.dj")

        form_data = MagicMock()
        form_data.get.return_value = "from_form.dj"
        request.form = AsyncMock(return_value=form_data)

        result = await extract_yak_path(request)
        assert result == "from_query.dj"

    @pytest.mark.asyncio
    async def test_extract_from_query_params(self) -> None:
        request = _mock_request(method="GET", headers_get_return=None, query_params_get_return="category/file.dj")

        result = await extract_yak_path(request)
        assert result == "category/file.dj"

    @pytest.mark.asyncio
    async def test_extract_empty_from_query_params(self) -> None:
        request = _mock_request(method="GET", headers_get_return=None, query_params_get_return="")

        result = await extract_yak_path(request)
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_none_from_query_params(self) -> None:
        request = _mock_request(method="GET", headers_get_return=None, query_params_get_return=None)

        result = await extract_yak_path(request)
        assert result == ""
