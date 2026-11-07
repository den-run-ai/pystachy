"""Owned host buffers and explicit completions for a local reference backend.

The same source runs in Pystachy and CPython with tools/rt_cpython on PYTHONPATH.
Private handles are implementation details, not an interface for raw pointers.
"""

from _thread import get_ident
from ffi import bytes_at, c_int, c_int64, c_size_t, c_void_p, extern


@extern("libpystachy_comm.so")
def cc_create(capacity: c_int64, byte_limit: c_int64) -> c_void_p: ...


@extern("libpystachy_comm.so")
def cc_close(ctx: c_void_p) -> None: ...


@extern("libpystachy_comm.so")
def cc_buffer(ctx: c_void_p, dtype: c_int64, count: c_int64) -> c_int64: ...


@extern("libpystachy_comm.so")
def cc_view(ctx: c_void_p, buffer_id: c_int64, offset: c_int64, count: c_int64) -> c_int64: ...


@extern("libpystachy_comm.so")
def cc_release_buffer(ctx: c_void_p, buffer_id: c_int64) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_info(ctx: c_void_p, buffer_id: c_int64, out: list[c_int64], size: c_size_t) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_write_bytes(ctx: c_void_p, buffer_id: c_int64, data: bytes, size: c_size_t) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_read_bytes(ctx: c_void_p, buffer_id: c_int64, out: list[c_int64], size: c_size_t) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_write_f64(ctx: c_void_p, buffer_id: c_int64, data: list[float], size: c_size_t) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_read_f64(ctx: c_void_p, buffer_id: c_int64, out: list[float], size: c_size_t) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_submit(ctx: c_void_p, kind: c_int64, sources: list[c_int64], nsrc: c_size_t,
              destinations: list[c_int64], ndst: c_size_t, tag: c_int64) -> c_int64: ...


@extern("libpystachy_comm.so")
def cc_progress(ctx: c_void_p, budget: c_int64) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_cancel(ctx: c_void_p, request_id: c_int64) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_status(ctx: c_void_p, request_id: c_int64) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_peek(ctx: c_void_p, out: list[c_int64], size: c_size_t) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_ack(ctx: c_void_p, request_id: c_int64) -> c_int: ...


@extern("libpystachy_comm.so")
def cc_error(status: c_int) -> str: ...


def _checked(status: int) -> int:
    if status < 0:
        raise RuntimeError(cc_error(status))
    return status


class Completion:
    def __init__(self, request_id: int, tag: int, status: int, kind: int):
        self.request_id = request_id
        self.tag = tag
        self.status = status
        self.kind = kind


class Context:
    """Single-owner local reference engine; explicit close is required.

    Only progress executes work. Poll/peek never block or make progress. Terminal
    requests retain capacity and buffer leases until acknowledged. No callback
    enters Python, and no managed input pointer survives an FFI call.
    """

    def __init__(self, capacity: int = 16, byte_limit: int = 1048576):
        if capacity < 1 or capacity > 64:
            raise ValueError("capacity must be between 1 and 64")
        if byte_limit < 0 or byte_limit > 67108864:
            raise ValueError("byte_limit must be between 0 and 67108864")
        self._owner = get_ident()
        self._busy = False
        self._handle = cc_create(capacity, byte_limit)
        if self._handle == 0:
            raise MemoryError("could not create communication context")

    def _check_thread(self) -> None:
        if get_ident() != self._owner:
            raise RuntimeError("context belongs to another thread")
        if self._busy:
            raise RuntimeError("context operation is already in progress")

    def _open(self) -> int:
        if self._handle == 0:
            raise ValueError("context is closed")
        return self._handle

    def buffer(self, dtype: str, count: int) -> "Buffer":
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            code = 0
            if dtype == "u8":
                code = 1
            elif dtype == "f64":
                code = 2
            else:
                raise ValueError("dtype must be u8 or f64")
            buffer_id = _checked(cc_buffer(handle, code, count))
            try:
                return Buffer(self, buffer_id)
            except BaseException:
                _checked(cc_release_buffer(handle, buffer_id))
                raise
        finally:
            self._busy = False

    def from_bytes(self, data: bytes) -> "Buffer":
        result = self.buffer("u8", len(data))
        try:
            result.write_bytes(data)
            return result
        except BaseException:
            result.close()
            raise

    def from_f64(self, data: list[float]) -> "Buffer":
        result = self.buffer("f64", len(data))
        try:
            result.write_f64(data)
            return result
        except BaseException:
            result.close()
            raise

    def _submit(self, kind: int, sources: list["Buffer"], destinations: list["Buffer"], tag: int) -> int:
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            src: list[c_int64] = []
            dst: list[c_int64] = []
            for buffer in sources:
                src.append(buffer._in_context(self))
            for buffer in destinations:
                dst.append(buffer._in_context(self))
            return _checked(cc_submit(handle, kind, src, len(src), dst, len(dst), tag))
        finally:
            self._busy = False

    def copy(self, source: "Buffer", destination: "Buffer", tag: int = 0) -> int:
        return self._submit(1, [source], [destination], tag)

    def broadcast(self, source: "Buffer", destinations: list["Buffer"], tag: int = 0) -> int:
        return self._submit(2, [source], destinations, tag)

    def allgather(self, sources: list["Buffer"], destinations: list["Buffer"], tag: int = 0) -> int:
        return self._submit(3, sources, destinations, tag)

    def allreduce_sum(self, sources: list["Buffer"], destinations: list["Buffer"], tag: int = 0) -> int:
        return self._submit(4, sources, destinations, tag)

    def progress(self, budget: int = 1) -> int:
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            return _checked(cc_progress(handle, budget))
        finally:
            self._busy = False

    def test(self, request_id: int) -> bool:
        """Observe terminal state without releasing capacity or buffer leases."""
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            return _checked(cc_status(handle, request_id)) == 1
        finally:
            self._busy = False

    def cancel(self, request_id: int) -> bool:
        """Cancel queued local work; terminal notification still requires ack."""
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            return _checked(cc_cancel(handle, request_id)) == 1
        finally:
            self._busy = False

    def peek(self) -> Completion | None:
        """Observe oldest completion without consuming it; safe to retry."""
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            info: list[c_int64] = [0, 0, 0, 0]
            if _checked(cc_peek(handle, info, len(info))) == 0:
                return None
            return Completion(info[0], info[1], info[2], info[3])
        finally:
            self._busy = False

    def ack(self, request_id: int) -> None:
        """Release a terminal request, capacity and leases; consumed IDs fail."""
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            _checked(cc_ack(handle, request_id))
        finally:
            self._busy = False

    def poll(self) -> list[Completion]:
        """Consume at most one completion; [] means none is ready.

        Allocate the whole result before ack, so a conversion/allocation failure
        leaves the event available. Use peek/ack when application handling may fail.
        """
        self._check_thread()
        try:
            self._busy = True
            handle = self._open()
            results: list[Completion] = []
            info: list[c_int64] = [0, 0, 0, 0]
            if _checked(cc_peek(handle, info, len(info))) == 1:
                results.append(Completion(info[0], info[1], info[2], info[3]))
                _checked(cc_ack(handle, info[0]))
            return results
        finally:
            self._busy = False

    def close(self) -> None:
        self._check_thread()
        try:
            self._busy = True
            handle = self._handle
            self._handle = 0  # Also safe if a Python signal raises after C frees it.
            if handle != 0:
                cc_close(handle)
        finally:
            self._busy = False

    def __enter__(self) -> "Context":
        self._check_thread()
        self._open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


class Buffer:
    """Context-owned fixed host allocation/view; construct through Context.

    Closing the user handle is safe during work. The native request keeps its
    own reference and lease until ack; Context.close releases everything.
    """

    def __init__(self, context: Context, buffer_id: int):
        self._context = context
        self._id = buffer_id

    def _in_context(self, context: Context) -> int:
        if self._context is not context:
            raise ValueError("buffer belongs to another context")
        if self._id == 0:
            raise ValueError("buffer is closed")
        return self._id

    def metadata(self) -> list[int]:
        self._context._check_thread()
        try:
            self._context._busy = True
            handle = self._context._open()
            info: list[c_int64] = [0, 0, 0, 0, 0]
            _checked(cc_info(handle, self._in_context(self._context), info, len(info)))
            return info
        finally:
            self._context._busy = False

    def view(self, offset: int, count: int) -> "Buffer":
        self._context._check_thread()
        try:
            self._context._busy = True
            handle = self._context._open()
            buffer_id = _checked(cc_view(handle, self._in_context(self._context), offset, count))
            try:
                return Buffer(self._context, buffer_id)
            except BaseException:
                _checked(cc_release_buffer(handle, buffer_id))
                raise
        finally:
            self._context._busy = False

    def write_bytes(self, data: bytes) -> None:
        self._context._check_thread()
        try:
            self._context._busy = True
            handle = self._context._open()
            _checked(cc_write_bytes(handle, self._in_context(self._context), data, len(data)))
        finally:
            self._context._busy = False

    def to_bytes(self) -> bytes:
        self._context._check_thread()
        try:
            self._context._busy = True
            handle = self._context._open()
            info: list[c_int64] = [0, 0]
            _checked(cc_read_bytes(handle, self._in_context(self._context), info, len(info)))
            return bytes_at(info[0], info[1])
        finally:
            self._context._busy = False

    def write_f64(self, data: list[float]) -> None:
        self._context._check_thread()
        try:
            self._context._busy = True
            handle = self._context._open()
            _checked(cc_write_f64(handle, self._in_context(self._context), data, len(data)))
        finally:
            self._context._busy = False

    def to_f64(self) -> list[float]:
        self._context._check_thread()
        try:
            self._context._busy = True
            handle = self._context._open()
            info: list[c_int64] = [0, 0, 0, 0, 0]
            buffer_id = self._in_context(self._context)
            _checked(cc_info(handle, buffer_id, info, len(info)))
            if info[0] != 2:
                raise ValueError("buffer dtype is not f64")
            result = [0.0] * info[1]
            _checked(cc_read_f64(handle, buffer_id, result, len(result)))
            return result
        finally:
            self._context._busy = False

    def close(self) -> None:
        self._context._check_thread()
        if self._context._handle == 0:
            self._id = 0
            return
        self._context._check_thread()
        try:
            self._context._busy = True
            handle = self._context._open()
            buffer_id = self._id
            self._id = 0
            if buffer_id != 0:
                _checked(cc_release_buffer(handle, buffer_id))
        finally:
            self._context._busy = False

    def __enter__(self) -> "Buffer":
        self.metadata()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
