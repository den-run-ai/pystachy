"""Identical typed dispatch inputs for match and handwritten conditions."""
from dataclasses import dataclass
import sys
from time import perf_counter_ns


@dataclass
class Event:
    kind: int
    value: int


def literal_match(code: int) -> int:
    match code:
        case 200 | 201 | 202:
            return 1
        case 204:
            return 2
        case 400 | 401 | 403 | 404:
            return 3
        case 429:
            return 4
        case 500 | 503:
            return 5
        case _:
            return 0


def literal_if(code: int) -> int:
    if code == 200 or code == 201 or code == 202:
        return 1
    if code == 204:
        return 2
    if code == 400 or code == 401 or code == 403 or code == 404:
        return 3
    if code == 429:
        return 4
    if code == 500 or code == 503:
        return 5
    return 0


def tuple_match(event: tuple[int, int]) -> int:
    match event:
        case (0, value) if value < 0:
            return -value
        case (1 | 2, value):
            return value * 3
        case (kind, value):
            return kind - value


def tuple_if(event: tuple[int, int]) -> int:
    kind, value = event
    if kind == 0 and value < 0:
        return -value
    if kind == 1 or kind == 2:
        return value * 3
    return kind - value


def dataclass_match(event: Event) -> int:
    match event:
        case Event(0, value) if value < 0:
            return -value
        case Event(1 | 2, value):
            return value * 3
        case Event(kind=kind, value=value):
            return kind - value
    raise AssertionError("the concrete Event subject must match")


def dataclass_if(event: Event) -> int:
    kind, value = event.kind, event.value
    if kind == 0 and value < 0:
        return -value
    if kind == 1 or kind == 2:
        return value * 3
    return kind - value


def verify() -> None:
    codes = [200, 201, 202, 204, 400, 401, 403, 404, 429, 500, 503, -1, 42]
    expected = [1, 1, 1, 2, 3, 3, 3, 3, 4, 5, 5, 0, 0]
    for i in range(len(codes)):
        assert literal_match(codes[i]) == expected[i]
        assert literal_if(codes[i]) == expected[i]
    events = [(0, -3), (0, 0), (0, 4), (1, -2), (1, 7), (2, 3), (-1, 5), (4, -6)]
    totals = [3, 0, -4, -6, 21, 9, -6, 10]
    for i in range(len(events)):
        pair = events[i]
        event = Event(pair[0], pair[1])
        assert tuple_match(pair) == totals[i]
        assert tuple_if(pair) == totals[i]
        assert dataclass_match(event) == totals[i]
        assert dataclass_if(event) == totals[i]


def inputs(size: int, shape: str) -> tuple[list[int], list[tuple[int, int]], list[Event]]:
    codes = [200, 201, 202, 204, 400, 401, 403, 404, 429, 500, 503, -1, 42]
    literals: list[int] = []
    pairs: list[tuple[int, int]] = []
    events: list[Event] = []
    for i in range(size):
        code = codes[i % len(codes)]
        kind = i % 6 - 1
        value = i % 19 - 9
        if shape == "skewed" and i % 100 != 0:
            code = 200
            kind = 1
        literals.append(code)
        pairs.append((kind, value))
        events.append(Event(kind, value))
    return literals, pairs, events


def run_literals(values: list[int], use_match: bool, loops: int) -> int:
    total = 0
    if use_match:
        for _ in range(loops):
            for value in values:
                total += literal_match(value)
    else:
        for _ in range(loops):
            for value in values:
                total += literal_if(value)
    return total


def run_tuples(values: list[tuple[int, int]], use_match: bool, loops: int) -> int:
    total = 0
    if use_match:
        for _ in range(loops):
            for value in values:
                total += tuple_match(value)
    else:
        for _ in range(loops):
            for value in values:
                total += tuple_if(value)
    return total


def run_dataclasses(values: list[Event], use_match: bool, loops: int) -> int:
    total = 0
    if use_match:
        for _ in range(loops):
            for value in values:
                total += dataclass_match(value)
    else:
        for _ in range(loops):
            for value in values:
                total += dataclass_if(value)
    return total


def run(kind: str, use_match: bool, loops: int, literals: list[int], pairs: list[tuple[int, int]], events: list[Event]) -> int:
    if kind == "literal":
        return run_literals(literals, use_match, loops)
    if kind == "tuple":
        return run_tuples(pairs, use_match, loops)
    return run_dataclasses(events, use_match, loops)


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else "literal"
    variant = sys.argv[2] if len(sys.argv) > 2 else "match"
    shape = sys.argv[3] if len(sys.argv) > 3 else "mixed"
    loops = int(sys.argv[4]) if len(sys.argv) > 4 else 100
    size = int(sys.argv[5]) if len(sys.argv) > 5 else 1024
    if kind not in ["literal", "tuple", "dataclass"] or variant not in ["match", "if"] or shape not in ["mixed", "skewed"]:
        raise ValueError("expected literal|tuple|dataclass match|if mixed|skewed [loops] [size]")
    if loops < 1 or size < 1 or loops > 1000000 or size > 1000000:
        raise ValueError("loops and size must each be in 1..1000000")
    verify()
    literals, pairs, events = inputs(size, shape)
    use_match = variant == "match"
    # Construction, independent known-answer controls and one warm-up pass are
    # excluded from the kernel timer. Both variants process identical objects.
    run(kind, use_match, 1, literals, pairs, events)
    start = perf_counter_ns()
    total = run(kind, use_match, loops, literals, pairs, events)
    elapsed = perf_counter_ns() - start
    print(total)
    print(loops * size)
    print("kernel_wall_ns", elapsed, file=sys.stderr)


if __name__ == "__main__":
    main()
