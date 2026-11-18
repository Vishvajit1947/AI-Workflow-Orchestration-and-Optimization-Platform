"""
Minimal async file I/O used by the workspace services.

Provides the small subset of the `aiofiles` API these modules use (`open`, and
`os.makedirs/rmdir/remove/rename/stat/listdir/path.exists/path.isdir`) by running the
blocking call in a worker thread, so no extra dependency is needed.
"""
import asyncio
import builtins
import os as _os
from types import SimpleNamespace


class _AsyncFile:
    def __init__(self, *args, **kwargs):
        self._args, self._kwargs, self._f = args, kwargs, None

    async def __aenter__(self):
        self._f = await asyncio.to_thread(builtins.open, *self._args, **self._kwargs)
        return self

    async def __aexit__(self, *exc):
        await asyncio.to_thread(self._f.close)

    async def read(self, *args):
        return await asyncio.to_thread(self._f.read, *args)

    async def write(self, data):
        return await asyncio.to_thread(self._f.write, data)


def open(*args, **kwargs):  # noqa: A001 - mirrors aiofiles.open
    return _AsyncFile(*args, **kwargs)


def _wrap(fn):
    async def run(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    return run


os = SimpleNamespace(
    makedirs=_wrap(_os.makedirs),
    rmdir=_wrap(_os.rmdir),
    remove=_wrap(_os.remove),
    rename=_wrap(_os.rename),
    stat=_wrap(_os.stat),
    listdir=_wrap(_os.listdir),
    path=SimpleNamespace(exists=_wrap(_os.path.exists), isdir=_wrap(_os.path.isdir)),
)
