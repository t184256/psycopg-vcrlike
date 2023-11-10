# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Provide an async_postgresql fixture.

Follows https://github.com/ClearcodeHQ/pytest-postgresql/issues/646
"""

import typing

import psycopg
import pytest
from pytest_postgresql.janitor import DatabaseJanitor

if typing.TYPE_CHECKING:
    from pytest_postgresql.executor import PostgreSQLExecutor
    from pytest_postgresql.executor_noop import NoopExecutor


pytest_plugins = 'psycopg_vcrlike'  # test my own plugin


class _Loadable(typing.Protocol):
    def __call__(  # noqa: PLR0913
        self,
        user: str,
        host: str,
        port: str | int,
        dbname: str,
        password: str | None,
    ) -> None: ...  # protocol


def _async_postgresql(
    process_fixture_name: str,
    dbname: str | None = None,
    load: list[_Loadable | str] | None = None,
    isolation_level: psycopg.IsolationLevel | None = None,
) -> typing.Callable[
    [pytest.FixtureRequest],
    typing.AsyncIterator[psycopg.AsyncConnection[tuple[typing.Any, ...]]],
]:
    @pytest.fixture()
    async def postgresql_factory(
        request: pytest.FixtureRequest,
    ) -> typing.AsyncIterator[psycopg.AsyncConnection[tuple[typing.Any, ...]]]:
        proc_fixture: PostgreSQLExecutor | NoopExecutor
        proc_fixture = request.getfixturevalue(process_fixture_name)

        pg_host = proc_fixture.host
        pg_port = proc_fixture.port
        pg_user = proc_fixture.user
        pg_password = proc_fixture.password
        pg_options = proc_fixture.options
        pg_db = dbname or proc_fixture.dbname
        pg_load = load or []

        with DatabaseJanitor(
            pg_user,
            pg_host,
            pg_port,
            pg_db,
            proc_fixture.version,
            pg_password,
            isolation_level,
        ) as janitor:
            db_connection = await psycopg.AsyncConnection.connect(
                dbname=pg_db,
                user=pg_user,
                password=pg_password,
                host=pg_host,
                port=pg_port,
                options=pg_options,
            )
            for load_element in pg_load:
                janitor.load(load_element)
            yield db_connection
            await db_connection.close()

    return postgresql_factory


async_postgresql = _async_postgresql('postgresql_proc')
