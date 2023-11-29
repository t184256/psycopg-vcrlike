# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Helpers to work with files using aiofile (preferred)."""

import pathlib
import typing

import aiofiles
from aiofiles.os import makedirs, unlink

if typing.TYPE_CHECKING:
    ModeRead = typing.Literal['r+', 'r']  # non-exhaustive
    ModeWrite = typing.Literal['w', 'a']  # non-exhaustive


async def read_file(path: pathlib.Path, mode: 'ModeRead') -> str:
    async with aiofiles.open(path, mode) as f:
        return await f.read()


async def write_file(path: pathlib.Path, mode: 'ModeWrite', data: str) -> None:
    async with aiofiles.open(path, mode) as f:
        await f.write(data)


__all__ = ['makedirs', 'read_file', 'unlink', 'write_file']
