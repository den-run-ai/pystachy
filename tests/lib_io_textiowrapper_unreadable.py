# lib/io.py: reading a TextIOWrapper whose buffer is not readable raises io.UnsupportedOperation,
# which the program does not catch. (The wrapper is flushed first: CPython's, which the exception
# leaves unclosed, closes itself as the program ends, which would write what was waiting.)
from io import TextIOWrapper


class Sink:
    def __init__(self) -> None:
        self.closed = False

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def write(self, b: bytes) -> int:
        print("write", b)
        return len(b)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


t = TextIOWrapper(Sink(), encoding="utf-8")
print(t.write("é\n"))
t.flush()
print(t.read())
