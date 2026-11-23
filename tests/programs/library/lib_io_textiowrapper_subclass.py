# A subclass of io.TextIOWrapper, a class template (its buffer's type types its field), without an
# __init__ of its own: its objects are of the specialization that derives from the one its
# arguments make (#962)
from io import TextIOWrapper


class Raw:
    def __init__(self) -> None:
        self.closed = False
        self.data = b""

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
        self.data += b
        return len(b)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


t = TextIOWrapper(Raw(), encoding="utf-8")


class Log(TextIOWrapper):
    def line(self, s: str) -> None:
        self.write(s + "\n")


raw = Raw()
log = Log(raw, encoding="utf-8")
log.line("hello")
log.flush()
print(raw.data)
print(isinstance(log, TextIOWrapper))
