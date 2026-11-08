"""Experimental bounded TCP exchanges; runs with Pystachy and CPython's ffi twin."""

from _thread import get_ident
from ffi import bytes_at, c_int, c_int64, c_size_t, c_void_p, extern


@extern("libpystachy_uvio.so")
def uvio_create(capacity: c_int64, byte_limit: c_int64) -> c_void_p: ...


@extern("libpystachy_uvio.so")
def uvio_submit(loop: c_void_p, address: str, port: c_int64, data: bytes,
                size: c_size_t, timeout_ms: c_int64) -> c_int64: ...


@extern("libpystachy_uvio.so")
def uvio_step(loop: c_void_p, block: c_int) -> c_int: ...


@extern("libpystachy_uvio.so")
def uvio_peek(loop: c_void_p, info: list[c_int64], size: c_size_t) -> c_int: ...


@extern("libpystachy_uvio.so")
def uvio_release(loop: c_void_p, request_id: c_int64) -> c_int: ...


@extern("libpystachy_uvio.so")
def uvio_cancel(loop: c_void_p, request_id: c_int64) -> c_int: ...


@extern("libpystachy_uvio.so")
def uvio_close(loop: c_void_p) -> c_int: ...


@extern("libpystachy_uvio.so")
def uvio_error_name(status: c_int) -> str: ...


@extern("libpystachy_uvio.so")
def uvio_version() -> str: ...


def checked(status: int) -> int:
    if status < 0:
        raise OSError(uvio_error_name(status))
    return status


class Completion:
    def __init__(self, request_id: int, status: int, data: bytes):
        self.request_id = request_id
        self.status = status
        self.data = data

    def error_name(self) -> str:
        return uvio_error_name(self.status)


class Loop:
    """Own a loop on its creating thread; use with/finally for explicit cleanup.

    A request sends one byte string, shuts down writing, then reads until EOF.
    Accepted requests occupy a slot until run_once copies their terminal result.
    """

    def __init__(self, capacity: int = 16, byte_limit: int = 65536):
        if capacity < 1 or capacity > 64:
            raise ValueError("capacity must be between 1 and 64")
        if byte_limit < 1 or byte_limit > 1048576:
            raise ValueError("byte_limit must be between 1 and 1048576")
        self._owner = get_ident()
        self._busy = False
        self._ready: list[Completion] = []
        self._handle = uvio_create(capacity, byte_limit)
        if self._handle == 0:
            raise OSError("could not initialize libuv loop")
        self._byte_limit = byte_limit

    def _check_thread(self) -> None:
        if get_ident() != self._owner:
            raise RuntimeError("loop belongs to another thread")

    def _check_idle(self) -> None:
        self._check_thread()
        if self._busy:
            raise RuntimeError("loop operation is already in progress")

    def _open(self) -> int:
        self._check_thread()
        if self._handle == 0:
            raise ValueError("loop is closed")
        return self._handle

    def submit(self, address: str, port: int, data: bytes, timeout_ms: int = 1000) -> int:
        self._check_idle()
        try:
            self._busy = True
            handle = self._open()
            if port < 1 or port > 65535:
                raise ValueError("port must be between 1 and 65535")
            if timeout_ms < 1 or timeout_ms > 60000:
                raise ValueError("timeout_ms must be between 1 and 60000")
            if len(data) > self._byte_limit:
                raise ValueError("request exceeds byte_limit")
            return checked(uvio_submit(handle, address, port, data, len(data), timeout_ms))
        finally:
            self._busy = False

    def cancel(self, request_id: int) -> bool:
        """True when cancellation starts, False when already terminal; unknown IDs fail."""
        self._check_idle()
        try:
            self._busy = True
            return checked(uvio_cancel(self._open(), request_id)) == 1
        finally:
            self._busy = False

    def run_once(self, block: bool = True) -> list[Completion]:
        """Run one turn and copy available completions; a blocking turn can return []."""
        self._check_idle()
        try:
            self._busy = True
            handle = self._open()
            # Keep copied events if a later copy in this batch raises. Deliver that
            # bounded batch before another native turn, even when block is True.
            results = self._ready
            if not results:
                count = checked(uvio_step(handle, int(block)))
                info: list[c_int64] = [0, 0, 0, 0]
                # Only step runs callbacks; peek/release cannot add events here.
                for _ in range(count):
                    if checked(uvio_peek(handle, info, len(info))) != 1:
                        raise RuntimeError("completion queue changed during drain")
                    request_id = info[0]
                    try:
                        data = bytes_at(info[2], info[3])
                        results.append(Completion(request_id, info[1], data))
                    finally:
                        checked(uvio_release(handle, request_id))
            self._ready = []
            return results
        finally:
            self._busy = False

    def close(self) -> None:
        """Cancel pending work and finish native close callbacks before freeing the loop."""
        self._check_idle()
        try:
            self._busy = True
            handle = self._handle
            # A signal can raise immediately after ctypes returns from the freeing call.
            self._handle = 0
            if handle != 0:
                status = uvio_close(handle)
                if status < 0:
                    self._handle = handle  # C preserves the allocation on a close error.
                    checked(status)
            self._ready.clear()
        finally:
            self._busy = False

    def __enter__(self) -> "Loop":
        self._open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
