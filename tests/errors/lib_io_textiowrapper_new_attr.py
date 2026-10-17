# error: object has no attribute 'mode'
# (tokenize.open() sets an attribute of its own, which CPython's TextIOWrapper objects take in their __dict__)
from io import TextIOWrapper


class Raw:
    def __init__(self) -> None:
        self.closed = False

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return 0

    def read1(self, n: int) -> bytes:
        return b""

    def read(self, n: int = -1) -> bytes:
        return b""

    def write(self, b: bytes) -> int:
        return len(b)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


t = TextIOWrapper(Raw(), encoding="utf-8")
t.mode = "r"
