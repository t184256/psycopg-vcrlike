# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test main module of psycopg_vcrlike."""

import asyncio
import contextlib
import pathlib
import typing

import psycopg
import pytest

N = 100


@pytest.fixture()
def is_recording(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> bool:
    """Return whether we're recording."""
    cur = async_postgresql.cursor()
    assert cur.__class__ is psycopg.AsyncCursor
    assert cur.__class__.__name__ in {
        'RecordingAsyncCursor',
        'ReplayingStubAsyncCursor',
    }
    return cur.__class__.__name__ == 'RecordingAsyncCursor'


@pytest.fixture()
def recording_path(
    is_recording: bool,  # noqa: FBT001
) -> typing.Callable[[str], pathlib.Path]:
    """Return the function that returns the path used for recording."""

    def f(test_name: str) -> pathlib.Path:
        return pathlib.Path(
            'tests',
            'cassettes',
            'test_cancellation',
            f'{test_name}.psycopg.{"tmp" if is_recording else "yml"}',
        )

    return f


async def _table_len(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
    name: str,
) -> int:
    cur = async_postgresql.cursor()
    await cur.execute(f'SELECT * FROM {name}')  # noqa: S608
    ln = len(await cur.fetchall())
    await cur.close()
    return ln


async def _do_little(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> None:
    cur = async_postgresql.cursor()
    await cur.execute('DROP TABLE IF EXISTS t1')
    await cur.execute('CREATE TABLE t1 (i int, s varchar(50))')
    await cur.execute('INSERT INTO t1 VALUES (%s, %s)', (1, 'a'))
    await cur.execute('SELECT * FROM t1 ORDER BY i ASC')
    assert await cur.fetchall() == [(1, 'a')]
    await async_postgresql.commit()
    await cur.close()


async def _do_much(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
    many_times_over: bool = False,  # noqa: FBT001, FBT002
) -> None:
    cur = async_postgresql.cursor()
    await cur.execute('DROP TABLE IF EXISTS t2')
    await cur.execute('CREATE TABLE t2 (i int, s varchar(50))')
    for i in range(N):
        await cur.execute('INSERT INTO t2 VALUES (%s, %s)', (i, str(i)))
    for _ in range(N if many_times_over else 1):
        await cur.execute('SELECT * FROM t2 ORDER BY i ASC')
        assert len(await cur.fetchall()) == N
    await async_postgresql.commit()
    await cur.close()


@pytest.mark.vcr()
async def test_cancellation_sanity(
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> None:
    """Sanity-test some helpers."""
    await _do_little(async_postgresql)
    await _do_much(async_postgresql)


@pytest.mark.vcr()
async def test_cancellation_earlier(
    is_recording: bool,  # noqa: FBT001
    recording_path: typing.Callable[[str], pathlib.Path],
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> None:
    """Test cancellation earlier."""
    for _ in range(N):
        # Test
        t1 = asyncio.create_task(_do_little(async_postgresql))
        t2 = asyncio.create_task(asyncio.sleep(0))
        finished, unfinished = await asyncio.wait(
            [t1, t2],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if is_recording:
            assert (finished, unfinished) == ({t2}, {t1})
        for task in unfinished:
            task.cancel()
        for task in unfinished:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    if is_recording:
        # do not keep partly written stuff around
        recording_path('test_cancellation_earlier').unlink()

        # Write it all
        t1 = asyncio.create_task(_do_little(async_postgresql))
        t2 = asyncio.create_task(asyncio.sleep(0))
        finished, unfinished = await asyncio.wait([t1, t2])
        assert (finished, unfinished) == ({t1, t2}, set())


@pytest.mark.vcr()
async def test_cancellation_later(
    is_recording: bool,  # noqa: FBT001
    recording_path: typing.Callable[[str], pathlib.Path],
    async_postgresql: psycopg.AsyncConnection[tuple[typing.Any, ...]],
) -> None:
    """Test cancellation later."""
    for _ in range(N):
        # Test
        t1 = asyncio.create_task(_do_little(async_postgresql))
        t2 = asyncio.create_task(
            _do_much(async_postgresql, many_times_over=True),
        )
        finished, unfinished = await asyncio.wait(
            [t1, t2],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in unfinished:
            task.cancel()
        for task in unfinished:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if is_recording:
            assert (finished, unfinished) == ({t1}, {t2})
            assert (await _table_len(async_postgresql, 't2')) < N

    if is_recording:
        # do not keep partly written stuff around
        recording_path('test_cancellation_later').unlink()

        # Write it all
        t1 = asyncio.create_task(_do_little(async_postgresql))
        t2 = asyncio.create_task(_do_much(async_postgresql))
        finished, unfinished = await asyncio.wait([t1, t2])
        assert (finished, unfinished) == ({t1, t2}, set())
        assert (await _table_len(async_postgresql, 't2')) == N
