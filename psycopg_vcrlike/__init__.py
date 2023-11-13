# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Pytest plugin provided by psycopg_vcrlike."""

import io
import pathlib
import typing

import _pytest
import aiofiles
import aiofiles.os
import psycopg
import psycopg_pool
import pytest
import ruamel.yaml
from psycopg import AsyncConnection, AsyncCursor
from psycopg.abc import Params, Query
from psycopg.rows import Row

CursorRow = typing.TypeVar('CursorRow')


class _Request(typing.TypedDict):
    query: Query
    params: Params | None
    prepare: bool | None
    binary: bool | None


_Response = list[tuple[typing.Any, ...]]


async def _record(
    vcr_path: pathlib.Path,
    request: _Request,
    response: _Response | None,
) -> None:
    with io.StringIO() as sio:
        yaml = ruamel.yaml.YAML(typ='safe')
        yaml.dump([{'request': request, 'response': response}], sio)

        await aiofiles.os.makedirs(vcr_path.parent, exist_ok=True)
        async with aiofiles.open(vcr_path.with_suffix('.tmp'), 'a') as f:
            await f.write(sio.getvalue())


class _LimitedAsyncCursor:
    async def executemany(
        self,
        query: Query,
        params_seq: typing.Iterable[Params],
        *,
        returning: bool = False,
    ) -> None:
        raise NotImplementedError

    async def stream(
        self,  # noqa: PLR6301
        query: Query,  # noqa: ARG002
        params: Params | None = None,  # noqa: ARG002
        *,
        binary: bool | None = None,  # noqa: ARG002
    ) -> typing.AsyncIterator[Row]:
        raise NotImplementedError
        yield

    async def fetchmany(self, size: int = 0) -> list[Row]:
        raise NotImplementedError

    async def __aiter__(self) -> typing.AsyncIterator[Row]:
        raise NotImplementedError
        yield


def _recording_async_cursor(
    vcr_path: pathlib.Path,
) -> type[AsyncCursor[typing.Any]]:
    class RecordingAsyncCursor(AsyncCursor[typing.Any], _LimitedAsyncCursor):
        """Recording version of AsyncCursor."""

        async def execute(
            self: typing.Self,
            query: Query,
            params: Params | None = None,
            *,
            prepare: bool | None = None,
            binary: bool | None = None,
        ) -> typing.Self:
            """Execute a query or command to the database (recording)."""
            r = await super().execute(
                query,
                params,
                prepare=prepare,
                binary=binary,
            )
            try:
                results = await self.fetchall()
                await self.scroll(0, mode='absolute')
            except psycopg.ProgrammingError as e:
                if "the last operation didn't produce a result" not in str(e):
                    raise
                results = None
            request: _Request = {
                'query': query,
                'params': params,
                'prepare': prepare,
                'binary': binary,
            }
            await _record(vcr_path, request, results)
            return r

    return RecordingAsyncCursor


def _replaying_stub_classes(  # noqa: C901
    vcr_path: pathlib.Path,
) -> tuple[type, type, type]:
    class ReplayingStubAsyncCursor(_LimitedAsyncCursor):
        """Replaying stub of AsyncCursor."""

        async def _load_recording(self) -> None:
            async with aiofiles.open(vcr_path) as f:
                recording = await f.read()
            yaml = ruamel.yaml.YAML(typ='safe')
            self._recording = list(yaml.load(recording))

        async def execute(
            self: typing.Self,
            query: Query,
            params: Params | None = None,
            *,
            prepare: bool | None = None,
            binary: bool | None = None,
        ) -> typing.Self:
            await self._load_recording()
            request = {
                'query': query,
                'params': list(params) if params is not None else None,
                'prepare': prepare,
                'binary': binary,
            }
            for i, r in enumerate(self._recording):
                if request == r['request']:
                    self._recording.pop(i)
                    self._response = r['response']
                    break
            else:
                msg = 'no matching response in recording'
                raise RuntimeError(msg)
            return self

        def _assert_response(self) -> None:
            if not hasattr(self, '_recording'):
                msg = 'no loaded recording, execute a cached response'
                raise RuntimeError(msg)
            if not hasattr(self, '_response'):
                msg = 'no loaded response, execute a cached response'
                raise RuntimeError(msg)

        async def fetchall(self) -> list[tuple[typing.Any, ...]]:
            self._assert_response()
            r = [tuple(row) for row in self._response]
            self._response.clear()
            return r

        async def fetchone(self) -> tuple[typing.Any, ...] | None:
            self._assert_response()
            if self._response:
                return tuple(self._response.pop(0))
            return None

        async def close(self) -> None:
            pass

    class ReplayingStubAsyncConnection:
        """Replaying stub of AsyncConnection."""

        @typing.no_type_check
        @classmethod
        async def connect(
            cls,
            *a,  # noqa: ANN002, ARG003
            **kwa,  # noqa: ANN003, ARG003
        ) -> AsyncConnection[typing.Any]:
            return cls()

        @typing.no_type_check
        async def close(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            pass

        @typing.no_type_check
        async def execute(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            curr = self.cursor()
            return curr.execute(*a, **kwa)

        @typing.no_type_check
        def cursor(
            self,  # noqa: PLR6301
            *a,  # noqa: ARG002, ANN002
            **kwa,  # noqa: ARG002, ANN003
        ) -> None:
            return ReplayingStubAsyncCursor()

        @typing.no_type_check
        async def commit(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            pass

    @typing.no_type_check
    class ReplayingStubAsyncConnectionPool:
        """Replaying stub of AsyncConnectionPool."""

        @typing.no_type_check
        async def open(self, *a, **kwa) -> None:  # noqa: A003, ANN002, ANN003
            pass

        @typing.no_type_check
        async def close(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            pass

        @typing.no_type_check
        async def wait(self, *a, **kwa) -> None:  # noqa: ANN002, ANN003
            pass

        @typing.no_type_check
        @staticmethod
        async def check_connection(conn) -> None:  # noqa: ANN001
            pass

        @typing.no_type_check
        async def getconn(  # noqa: ANN202
            self,  # noqa: PLR6301
            timeout: float | None = None,  # noqa: ARG002
        ):
            return ReplayingStubAsyncConnection()

        @typing.no_type_check
        async def connection(  # noqa: ANN202
            self,  # noqa: PLR6301
            timeout: float | None = None,  # noqa: ARG002
        ):
            yield ReplayingStubAsyncConnection()

    return (
        ReplayingStubAsyncCursor,
        ReplayingStubAsyncConnection,
        ReplayingStubAsyncConnectionPool,
    )


# We're gonna extend pytest-recording
# with this fixture that replaces psycopg internals
# with either recording or playback versions
# depending on the mode and presence of cassettes
@pytest.fixture(autouse=True)
def _psycopg_vcrlike(
    request: _pytest.fixtures.SubRequest,
    record_mode: str,
    vcr_cassette_dir: str,
    default_cassette_name: str,
) -> typing.Iterator[None]:
    """Caches/replays asyncio psycopg SQL access for vcr-decorated tests."""
    vcr_path = pathlib.Path(
        vcr_cassette_dir,
        default_cassette_name + '.psycopg.yml',
    )
    under_vcr = list(request.node.iter_markers(name='vcr'))
    rewrite = record_mode == 'rewrite'
    vcr_path_exists = pathlib.Path(vcr_path).exists()

    _orig_cu = psycopg.AsyncCursor
    _orig_co = None
    _orig_cp = None
    conn_async = psycopg.connection_async
    pool_async = psycopg_pool.pool_async

    if not under_vcr:
        yield  # don't record anything, don't stub out anything
    elif rewrite or not vcr_path_exists:
        # record queries and results
        cu = _recording_async_cursor(vcr_path)
        conn_async.AsyncCursor = cu  # type: ignore[attr-defined,assignment]
        psycopg.cursor_async.AsyncCursor = cu  # type: ignore[misc,assignment]
        psycopg.AsyncCursor = cu  # type: ignore[misc,assignment]
        vcr_path.with_suffix('.tmp').unlink(missing_ok=True)
        yield  # record
        vcr_path.with_suffix('.tmp').rename(vcr_path)
    else:
        # replay queries and results
        _orig_co = conn_async.AsyncConnection
        _orig_cp = psycopg_pool.pool_async.AsyncConnectionPool
        cu, co, cp = _replaying_stub_classes(vcr_path)
        conn_async.AsyncCursor = cu  # type: ignore[attr-defined,assignment]
        psycopg.cursor_async.AsyncCursor = cu  # type: ignore[misc,assignment]
        psycopg.AsyncCursor = cu  # type: ignore[misc,assignment]
        conn_async.AsyncConnection = co  # type: ignore[misc,assignment]
        psycopg.AsyncConnection = co  # type: ignore[misc,assignment]
        pool_async.AsyncConnection = (  # type: ignore[attr-defined,assignment]
            co,
        )
        pool_async.AsyncConnectionPool = cp  # type: ignore[misc,assignment]
        psycopg_pool.AsyncConnectionPool = cp  # type: ignore[misc,assignment]
        yield  # replay

    conn_async.AsyncCursor = _orig_cu  # type: ignore[attr-defined]
    psycopg.cursor_async.AsyncCursor = _orig_cu  # type: ignore[misc]
    psycopg.AsyncCursor = _orig_cu  # type: ignore[misc]

    if _orig_co is not None:
        conn_async.AsyncConnection = _orig_co  # type: ignore[misc]
        psycopg.AsyncConnection = _orig_co  # type: ignore[misc]
        pool_async.AsyncConnection = _orig_co  # type: ignore[attr-defined]

    if _orig_cp is not None:
        pool_async.AsyncConnectionPool = _orig_cp  # type: ignore[misc]
        psycopg_pool.AsyncConnectionPool = _orig_cp  # type: ignore[misc]


__all__: list[str] = []
