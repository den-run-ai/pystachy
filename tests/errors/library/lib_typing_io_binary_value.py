# error: expected file | StringIO, got BytesIO
from io import BytesIO
from typing import IO


def text(stream: IO[str]) -> str:
    return stream.read()


print(text(BytesIO(b"binary")))
