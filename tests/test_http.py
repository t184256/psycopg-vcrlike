# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test that the plugin doesn't break regular aiohttp recording."""

import typing

import aiohttp
import pytest


@pytest.mark.vcr()
async def test_smoke_aiohttp() -> None:
    """Test that python-recording still works."""
    url = 'https://example.org'
    async with aiohttp.ClientSession() as sess, sess.get(url) as response:
        html = await response.text()
        assert '<title>Example Domain</title>' in html


# pytest-recording configuration


_SCRUB_HEADERS_RESPONSE = ('Age', 'Date', 'Etag', 'Expires', 'Server')


def _scrub_response(
    response: dict[str, dict[str, bytes]],
) -> dict[str, dict[str, bytes]]:
    headers = response['headers'].copy()
    for h in _SCRUB_HEADERS_RESPONSE:
        if h in headers:
            del headers[h]
    response['headers'] = headers
    return response


@pytest.fixture(scope='session', autouse=True)
def vcr_config() -> dict[str, typing.Any]:
    """Filter out sensitive info from cassettes."""
    return {
        'before_record_response': _scrub_response,
        'decode_compressed_response': True,
    }
