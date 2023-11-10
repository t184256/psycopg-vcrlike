# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test main module of psycopg_vcrlike."""

import pathlib
import typing

import psycopg
import pytest


@pytest.mark.vcr()  # that's it, that's everything needed
async def test_fetchall(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> None:
    """Test .fetchall recording/replaying."""
    cur = async_postgresql.cursor()
    await cur.execute('CREATE TABLE t (i int, s varchar(50))')
    await cur.execute('INSERT INTO t VALUES (%s, %s)', (2, 'b'))
    await cur.execute('INSERT INTO t VALUES (%s, %s)', (1, 'a'))
    await cur.execute('SELECT * FROM t ORDER BY i ASC')
    assert await cur.fetchall() == [(1, 'a'), (2, 'b')]
    await async_postgresql.commit()
    await cur.close()

    _assert_cassette(cur, 'test_fetchall')


@pytest.mark.vcr()
async def test_fetchone(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> None:
    """Test .fetchone recording/replaying."""
    cur = async_postgresql.cursor()
    await cur.execute('CREATE TABLE o (i int, s varchar(50))')
    await cur.execute('INSERT INTO o VALUES (%s, %s)', (2, 'b'))
    await cur.execute('INSERT INTO o VALUES (%s, %s)', (1, 'a'))
    await cur.execute('SELECT * FROM o ORDER BY i ASC')
    assert await cur.fetchone() == (1, 'a')
    assert await cur.fetchone() == (2, 'b')
    assert await cur.fetchone() is None
    await async_postgresql.commit()
    await cur.close()

    _assert_cassette(cur, 'test_fetchone')


def _assert_cassette(
    cur: psycopg.AsyncCursor[typing.Any],
    test_name: str,
) -> None:
    assert cur.__class__ is psycopg.AsyncCursor
    assert cur.__class__.__name__ in {
        'RecordingAsyncCursor',
        'ReplayingStubAsyncCursor',
    }
    recording = cur.__class__.__name__ == 'RecordingAsyncCursor'
    p = pathlib.Path(
        'tests',
        'cassettes',
        'test_smoke',
        f'{test_name}.psycopg.{"tmp" if recording else "yml"}',
    )
    assert p.exists()
