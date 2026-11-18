# A parameter annotated bytes | bytearray takes either. The function is compiled for each type:
# it reads a bytearray's bytes in place, and the object it has is the caller's own.
from typing import Callable


def total(data: bytes | bytearray) -> int:
    t = 0
    for x in data:
        t += x
    return t + (1000 if isinstance(data, bytearray) else 0)


def same(data: bytes | bytearray) -> bytes | bytearray:
    return data


def first(data: "bytearray | bytes", i: int = 0) -> int:
    return data[i]


def fill(data: bytes | bytearray, x: int) -> bool:
    # (a bytearray is the caller's object: a change here is seen there)
    if isinstance(data, bytes):
        return False
    data[0] = x
    data.append(x)
    return True


def both(a: bytes | bytearray, b: bytes | bytearray = b"-") -> bytes:
    return bytes(a) + bytes(b)


def head(data: bytes | bytearray, n: int = 2) -> bytes | bytearray:
    return data[:n]


def apply(f: Callable[[bytes], int], x: bytes) -> int:
    return f(x)


def chunks(data: bytes | bytearray, n: int):
    for i in range(0, len(data), n):
        yield bytes(data[i:i + n])


def depth(data: bytes | bytearray, n: int) -> int:
    return len(data) if n == 0 else depth(data, n - 1) + 1


class Sink:
    def __init__(self) -> None:
        self.n = 0
        self.arrays = 0

    def feed(self, data: bytes | bytearray) -> None:
        self.n += len(data)
        if not isinstance(data, bytes):
            self.arrays += 1

    @staticmethod
    def last(data: bytes | bytearray) -> int:
        return data[-1]


class Loud(Sink):
    def feed(self, data: bytes | bytearray) -> None:
        self.n += 100 * len(data)


def main() -> None:
    b = bytearray(b"\x01\x02\x03")
    print(total(b"\x01\x02\x03"), total(b), same(b) is b, same(b"x"), first(b, 2), first(b"\x09"))
    print(fill(b"ab", 7), fill(b, 7), b, total(data=b))
    print(both(b), both(b"x", b), both(b=b"y", a=b), head(b), head(b"abc", 1), head(bytearray(b"wxyz"), n=3))
    print(apply(total, b"\x05\x06"), list(map(total, [b"\x05", b"\x06"])), list(chunks(b, 3)), list(chunks(b"abcde", 2)))
    print(depth(b, 3), depth(b"12", 2))
    sinks: list[Sink] = [Sink(), Loud()]
    for s in sinks:
        s.feed(b)
        s.feed(b"ab")
        u = s.feed
        u(b)
    print([s.n for s in sinks], [s.arrays for s in sinks], Sink.last(b), Sink.last(b"\x08"), sinks[0].last(b))
    maybe: bytes | None = b"\x07abc" if len(b) > 1 else None
    if maybe is not None:
        print(total(maybe), first(maybe, 1))
    b.clear()
    try:
        first(b)
    except IndexError as e:
        print("IndexError:", e)
    try:
        first(b"")
    except IndexError as e:
        print("IndexError:", e)


main()
