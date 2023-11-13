# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test that the plugin doesn't break regular aiohttp recording."""

import aiohttp
import pytest


@pytest.mark.vcr()
async def test_smoke_aiohttp() -> None:
    """Test that python-recording still works."""
    url = 'https://example.org'
    async with aiohttp.ClientSession() as sess, sess.get(url) as response:
        html = await response.text()
        assert '<title>Example Domain</title>' in html
