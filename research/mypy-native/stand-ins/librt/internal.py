"""Probe stand-in for librt.internal (signatures from mypy 2.4.1's typeshed stub); bodies raise."""


class ReadBuffer:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.pos = 0


class WriteBuffer:
    def __init__(self) -> None:
        self.parts: list[bytes] = []

    def getvalue(self) -> bytes:
        return b"".join(self.parts)


def write_bool(data: WriteBuffer, value: bool, /) -> None:
    raise NotImplementedError("librt.internal.write_bool")


def read_bool(data: ReadBuffer, /) -> bool:
    raise NotImplementedError("librt.internal.read_bool")


def write_str(data: WriteBuffer, value: str, /) -> None:
    raise NotImplementedError("librt.internal.write_str")


def read_str(data: ReadBuffer, /) -> str:
    raise NotImplementedError("librt.internal.read_str")


def write_bytes(data: WriteBuffer, value: bytes, /) -> None:
    raise NotImplementedError("librt.internal.write_bytes")


def read_bytes(data: ReadBuffer, /) -> bytes:
    raise NotImplementedError("librt.internal.read_bytes")


def write_float(data: WriteBuffer, value: float, /) -> None:
    raise NotImplementedError("librt.internal.write_float")


def read_float(data: ReadBuffer, /) -> float:
    raise NotImplementedError("librt.internal.read_float")


def write_int(data: WriteBuffer, value: int, /) -> None:
    raise NotImplementedError("librt.internal.write_int")


def read_int(data: ReadBuffer, /) -> int:
    raise NotImplementedError("librt.internal.read_int")


def write_tag(data: WriteBuffer, value: int, /) -> None:
    raise NotImplementedError("librt.internal.write_tag")


def read_tag(data: ReadBuffer, /) -> int:
    raise NotImplementedError("librt.internal.read_tag")


def cache_version() -> int:
    return 0


def extract_symbol(data: ReadBuffer, /) -> bytes:
    raise NotImplementedError("librt.internal.extract_symbol")
