# Minimal shim for aiofiles used in tests when real file IO isn't needed.
# Provides an async context manager 'open' that writes to a BytesIO in memory.
import io
import types

class _AIOFile:
    def __init__(self, path, mode):
        self._buf = io.BytesIO()
    async def write(self, b):
        return self._buf.write(b)
    async def read(self, n=-1):
        return self._buf.read(n)
    async def close(self):
        return

class _Open:
    def __init__(self, path, mode):
        self.path = path
        self.mode = mode
    async def __aenter__(self):
        return _AIOFile(self.path, self.mode)
    async def __aexit__(self, exc_type, exc, tb):
        return

async def open(path, mode='rb'):
    return _Open(path, mode)

__all__ = ['open']
