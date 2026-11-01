# Native calls use the shipped helper; CPython loads its unchanged scalar source.
from typing import Callable

try:
    from _pystachy_bytescan import scan
except ImportError:
    from bytescan_oracle import scan


def indirect(fn: Callable[[bytes, int, int, int, int, int], int], data: bytes) -> int:
    return fn(data, 0, len(data), 34, 92, 32)


events: list[str] = []


def number(name: str, value: int) -> int:
    events.append(name)
    return value


def data_arg() -> bytes:
    events.append("data")
    return b'abcdefgh"tail'


def main() -> None:
    cases: list[tuple[bytes, int, int, int, int, int, int]] = [
        (b"", 0, 0, 34, 92, 32, 0),
        (b"abcdefgh", 0, 8, 34, 92, 32, 8),
        (b"xxxAxxxB", 0, 8, 65, 66, 0, 3),
        (b"xxxBxxxA", 4, 8, 65, 66, 0, 7),
        (b"01234567A", 0, 8, 65, 66, 0, 8),
        (b"01234567A", 8, 8, 65, 66, 0, 8),
        (b"01234567A", 0, 9, 65, 66, 0, 8),
        (b"\xff\xfe\x80ABC\x00", 0, 7, 34, 92, 32, 6),
        (b"\xff\xfe\x80\x7fABC", 0, 7, 34, 92, 128, 3),
        (b"\xff\xfe\x80\x7fABC", 0, 7, 34, 92, 129, 2),
        (b"\xff\xfe\x80\x7fABC", 0, 7, 34, 92, 256, 0),
        (b"abcdefgh\xfftail", 0, 13, 255, 255, 0, 8),
        (b"abcdefgh\x80tail", 0, 13, 128, 255, 0, 8),
        (b"abcdefgh\x00tail", 0, 13, 0, 0, 0, 8),
    ]
    for data, start, end, first, second, below, expected in cases:
        assert scan(data, start, end, first, second, below) == expected
        assert scan(data=data, below=below, end=end, first=first, start=start, second=second) == expected
    print("predicate-cases", len(cases))
    print("callable", indirect(scan, b"abcdefgh\\tail"), indirect(scan, b"short"))

    assert scan(data_arg(), number("start", 0), number("end", 12), number("first", 34),
                number("second", 92), number("below", 32)) == 8
    print("positional-order", events)
    events.clear()
    assert scan(below=number("below", 32), data=data_arg(), end=number("end", 12),
                second=number("second", 92), start=number("start", 0), first=number("first", 34)) == 8
    print("keyword-order", events)

    for start, end in [(-1, 3), (0, -1), (4, 3), (0, 4), (-9223372036854775807, 3), (0, 9223372036854775807)]:
        try:
            scan(b"abc", start, end, 34, 92, 32)
            assert False
        except IndexError as exc:
            print("bounds", exc)
    for first, second, below in [(-1, 92, 32), (256, 92, 32), (34, -1, 32),
                                 (34, 256, 32), (34, 92, -1), (34, 92, 257)]:
        try:
            scan(b"", 0, 0, first, second, below)
            assert False
        except ValueError as exc:
            print("predicate", exc)
    try:
        scan(b"abc", -1, 3, -1, 92, 257)
        assert False
    except IndexError as exc:
        print("bounds-before-predicate", exc)


main()
