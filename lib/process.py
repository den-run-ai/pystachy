"""Experimental owned process workers; see docs/process-workers.md.

Linux executable/JIT owners, explicit absolute argv, and binary pipes. This small
API uses ordinary Python syntax and also runs under CPython. A context
manager (or explicit close) bounds the child lifetime, including descendants.
"""
import _pystachy_process


class Popen:
    _handle: int
    pid: int

    def __init__(self, args: list[str]) -> None:
        self._handle = _pystachy_process.spawn(args)
        self.pid = _pystachy_process.pid(self._handle)

    def poll(self) -> int | None:
        status = _pystachy_process.poll(self._handle)
        return None if status == 9223372036854775807 else status

    @property
    def returncode(self) -> int | None:
        return self.poll()

    def wait(self, timeout: float = -1.0) -> int:
        return _pystachy_process.wait(self._handle, float(timeout))

    def communicate(self, input: bytes = b"", timeout: float = -1.0,
                    max_output_bytes: int = 16777216) -> tuple[bytes, bytes]:
        return _pystachy_process.communicate(self._handle, input, float(timeout), max_output_bytes)

    def terminate(self) -> None:
        _pystachy_process.signal(self._handle, 15)

    def kill(self) -> None:
        _pystachy_process.signal(self._handle, 9)

    def close(self) -> None:
        _pystachy_process.close(self._handle)
        self._handle = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def run(args: list[str], input: bytes = b"", timeout: float = -1.0,
        max_output_bytes: int = 16777216) -> tuple[int, bytes, bytes]:
    with Popen(args) as child:
        stdout, stderr = child.communicate(input, timeout, max_output_bytes)
        return child.wait(), stdout, stderr
