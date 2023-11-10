# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test main module of psycopg_vcrlike."""

import pathlib
import typing

import psycopg


async def test_async_postgresql(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> None:
    """Test that async_postgresql fixture works."""
    cur = async_postgresql.cursor()
    await cur.execute(
        'CREATE TABLE test (id serial PRIMARY KEY, data varchar);',
    )
    await async_postgresql.commit()
    res = await cur.execute(
        'SELECT 4;',
    )
    assert await res.fetchall() == [(4,)]
    await async_postgresql.commit()
    await cur.close()

    p = pathlib.Path('tests', 'cassettes', 'test_async_postgresql')
    assert not p.exists()
