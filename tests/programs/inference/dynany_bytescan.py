# pystachy: dynamic-any
from typing import Any, Callable

try:
    from _pystachy_bytescan import scan
except ImportError:
    from bytescan_oracle import scan

events: list[str] = []
global_start = int("1000")


class Positions:
    def __init__(self, start: int) -> None:
        self.start = start


def number(name: str, value: int) -> int:
    events.append(name)
    return value


def data_arg() -> bytes:
    events.append("data")
    return b"x" * 1000 + b'"'


def reset_global() -> int:
    global global_start
    global_start = 0
    return 1001


def reset_field(positions: Positions) -> int:
    positions.start = 0
    return 1001


def reset_list(positions: list[int]) -> int:
    positions[0] = 0
    return 1001


def throwing() -> int:
    events.append("second")
    raise RuntimeError("argument failed")


def main() -> None:
    offset = int("1000")
    through: Callable[[bytes, int, int, int, int, int], int] = scan
    for hit in [False, True]:
        data = b"x" * 1000 + (b'"' if hit else b"")
        start = offset if hit else 0
        end = 1001 if hit else offset
        direct: Any = scan(data, start, end, 34, 92, 32)
        keyword: Any = scan(data=data, start=start, end=end, first=34, second=92, below=32)
        called: Any = through(data, start, end, 34, 92, 32)
        print("initial" if hit else "end", direct, direct is offset, keyword is offset, called is offset)
    data = b"x" * 1000 + b'"'
    saved: Any = None
    alias: Any = offset
    print("walrus", scan(data, (saved := offset), 1001, 34, 92, 32), saved is offset)
    print("local-alias", scan(data, offset, 1001, 34, 92, 32), alias is offset)
    result = scan(data, global_start, reset_global(), 34, 92, 32)
    print("global-snapshot", result, global_start)
    positions = Positions(offset)
    field_alias: Any = positions.start
    result = scan(data, positions.start, reset_field(positions), 34, 92, 32)
    print("field-snapshot", result, positions.start, field_alias is offset)
    items = [offset]
    item_alias: Any = items[0]
    result = scan(data, items[0], reset_list(items), 34, 92, 32)
    print("list-snapshot", result, items[0], item_alias is offset)
    result = scan(data_arg(), number("start", 0), number("end", 1001),
                  number("first", 34), number("second", 92), number("below", 32))
    print("argument-order", result, events)
    events.clear()
    try:
        scan(data_arg(), number("start", -1), number("end", 1001),
             number("first", -1), throwing(), number("below", 257))
        assert False
    except RuntimeError as exc:
        print("argument-before-validation", exc, events)
    events.clear()
    try:
        scan(data_arg(), number("start", -1), number("end", 1001),
             number("first", -1), number("second", 92), number("below", 257))
        assert False
    except IndexError as exc:
        print("validation-after-arguments", exc, events)
    # CPython checks these in the scalar body; native code also checks annotations.
    bad: Any = None
    for position in range(1, 6):
        try:
            if position == 1:
                scan(b"", bad, 0, 34, 92, 32)
            elif position == 2:
                scan(b"", 0, bad, 34, 92, 32)
            elif position == 3:
                scan(b"", 0, 0, bad, 92, 32)
            elif position == 4:
                scan(b"", 0, 0, 34, bad, 32)
            else:
                scan(b"", 0, 0, 34, 92, bad)
            assert False
        except TypeError:
            print("none", position + 1)


main()
