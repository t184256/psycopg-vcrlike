# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Helpers to work with files with no external libraries."""

import asyncio
import pathlib
import typing

if typing.TYPE_CHECKING:
    ModeRead = typing.Literal['r+', 'r']  # non-exhaustive
    ModeWrite = typing.Literal['w', 'a']  # non-exhaustive


async def makedirs(
    path: pathlib.Path,
    parents: bool = False,  # noqa: FBT001,FBT002
    mode: int = 0o777,
    exist_ok: bool = False,  # noqa: FBT001,FBT002
) -> None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        path.mkdir,
        mode,
        parents,
        exist_ok,
    )


async def unlink(
    path: pathlib.Path,
    missing_ok: bool = False,  # noqa: FBT001,FBT002
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, path.unlink, missing_ok)


async def read_file(path: pathlib.Path, mode: 'ModeRead') -> str:
    # not async
    with path.open(mode) as f:
        return f.read()


async def write_file(path: pathlib.Path, mode: 'ModeWrite', data: str) -> None:
    with path.open(mode) as f:
        f.write(data)


__all__ = ['makedirs', 'read_file', 'unlink', 'write_file']
