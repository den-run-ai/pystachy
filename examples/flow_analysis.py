"""Opt-in flow-analysis prototype; also runs unchanged under CPython.

PYSTACHY_FLOW_LOCALS=1 PYSTACHY_CLOSED_UNIONS=1 ./pystachy run examples/flow_analysis.py
"""


def parse_count(text):
    value = text.strip()
    value = int(value)
    return value + 1


def mean(values: list[int]) -> float:
    total = 0
    for value in values:
        total += value
    total = total / len(values)
    return total


def decode(value: int | str | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value + 1
    return int(value)


def event_label(code: int) -> str:
    # The representation is explicit at the join; operations follow a tag test.
    payload: int | str = 0
    if code > 0:
        payload = "ready"
    else:
        payload = code
    if isinstance(payload, str):
        return payload.upper()
    return str(payload - 1)


def twice(value):
    return value + value


print(parse_count(" 41 "))
print(mean([1, 2, 4]))
print(decode(None), decode(3), decode("12"))
print(event_label(1), event_label(-2))
# These repeated contexts reuse two existing template specializations.
print(twice(2), twice(3), twice("a"), twice("b"))
