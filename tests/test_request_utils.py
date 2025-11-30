"""Tests for the request utilities module."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from yak_shears._yak.request_utils import extract_yak_path, is_htmx_request


def _mock_request(**kwargs) -> Request:
    """Create a mock request with spec=Request for beartype compatibility."""
    return MagicMock(spec=Request, **kwargs)


class TestIsHtmxRequest:
    def test_htmx_request_true(self):
        request = _mock_request()
        request.headers.get.return_value = "true"
        assert is_htmx_request(request) is True

    def test_htmx_request_false(self):
        request = _mock_request()
        request.headers.get.return_value = None
        assert is_htmx_request(request) is False

    def test_htmx_request_other_value(self):
        request = _mock_request()
        request.headers.get.return_value = "false"
        assert is_htmx_request(request) is False


class TestExtractYakPath:
    @pytest.mark.asyncio
    async def test_extract_from_htmx_form(self):
        request = _mock_request()
        request.headers.get.return_value = "true"
        request.method = "POST"

        form_data = MagicMock()
        form_data.get.return_value = "category/file.dj"
        request.form = AsyncMock(return_value=form_data)

        result = await extract_yak_path(request)
        assert result == "category/file.dj"

    @pytest.mark.asyncio
    async def test_extract_from_post_form(self):
        request = _mock_request()
        request.headers.get.return_value = None
        request.method = "POST"
        request.query_params.get.return_value = ""

        form_data = MagicMock()
        form_data.get.return_value = "category/file.dj"
        request.form = AsyncMock(return_value=form_data)

        result = await extract_yak_path(request)
        assert result == "category/file.dj"

    @pytest.mark.asyncio
    async def test_extract_prefers_query_params_over_form(self):
        request = _mock_request()
        request.headers.get.return_value = None
        request.method = "POST"
        request.query_params.get.return_value = "from_query.dj"

        form_data = MagicMock()
        form_data.get.return_value = "from_form.dj"
        request.form = AsyncMock(return_value=form_data)

        result = await extract_yak_path(request)
        assert result == "from_query.dj"

    @pytest.mark.asyncio
    async def test_extract_from_query_params(self):
        request = _mock_request()
        request.headers.get.return_value = None
        request.method = "GET"
        request.query_params.get.return_value = "category/file.dj"

        result = await extract_yak_path(request)
        assert result == "category/file.dj"

    @pytest.mark.asyncio
    async def test_extract_empty_from_query_params(self):
        request = _mock_request()
        request.headers.get.return_value = None
        request.method = "GET"
        request.query_params.get.return_value = ""

        result = await extract_yak_path(request)
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_none_from_query_params(self):
        request = _mock_request()
        request.headers.get.return_value = None
        request.method = "GET"
        request.query_params.get.return_value = None

        result = await extract_yak_path(request)
        assert result == ""
