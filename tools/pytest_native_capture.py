"""The capsys and capfd fixtures for generated native tests.

Generated modules import this only when a test or fixture requests one of them. This
is not pytest's implementation: both fixtures send descriptors 1 and 2 to files, as
pytest's capfd does, because a compiled print() writes to descriptor 1 whatever
sys.stdout names.
"""

import os
import sys
import tempfile
from typing import NamedTuple


class CaptureResult(NamedTuple):
    out: str
    err: str


class Stream:
    """One standard stream, sent to a file between start() and stop()."""

    def __init__(self, descriptor: int, path: str) -> None:
        self.descriptor = descriptor
        self.path = path
        self.position = 0
        self.saved = -1

    def start(self) -> None:
        self.saved = os.dup(self.descriptor)
        with open(self.path, "a") as target:
            os.dup2(target.fileno(), self.descriptor)

    def stop(self) -> None:
        if self.saved >= 0:
            os.dup2(self.saved, self.descriptor)
            os.close(self.saved)
            self.saved = -1

    def read(self) -> str:
        """What was written since the last read."""
        with open(self.path) as source:
            text = source.read()
        fresh = text[self.position:]
        self.position = len(text)
        return fresh


class Disabled:
    """`with capsys.disabled():` output reaches the real streams inside the block."""

    def __init__(self, capture: "Capture") -> None:
        self.capture = capture

    def __enter__(self) -> None:
        self.capture.stop()

    def __exit__(self, kind: object, value: object, traceback: object) -> None:
        self.capture.start()


class Capture:
    def __init__(self, directory: str) -> None:
        self.directory = directory
        self.out = Stream(1, os.path.join(directory, "out"))
        self.err = Stream(2, os.path.join(directory, "err"))
        self.start()

    def start(self) -> None:
        sys.stdout.flush()
        sys.stderr.flush()
        self.out.start()
        self.err.start()

    def stop(self) -> None:
        sys.stdout.flush()
        sys.stderr.flush()
        self.out.stop()
        self.err.stop()

    def readouterr(self) -> CaptureResult:
        sys.stdout.flush()
        sys.stderr.flush()
        return CaptureResult(self.out.read(), self.err.read())

    def disabled(self) -> Disabled:
        return Disabled(self)

    def close(self) -> None:
        self.stop()
        for path in (self.out.path, self.err.path):
            if os.path.exists(path):
                os.remove(path)
        os.rmdir(self.directory)


def capture():
    captured = Capture(tempfile.mkdtemp())
    yield captured
    captured.close()
