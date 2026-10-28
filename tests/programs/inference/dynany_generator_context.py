# pystachy: dynamic-any
# Fresh yielded lists use their direct consumer's layout; ordinary calls retain
# dynamic items. No already-yielded list or existing iterator is converted.
from typing import Any, Iterator


def rows(value: int) -> Iterator[list[Any]]:
    yield [value, value + 1]
    yield []


def forwarded(value: int) -> Iterator[list[Any]]:
    yield from rows(value)


def concrete(value: int) -> Iterator[list[int]]:
    yield from forwarded(value)


loose = rows(1)
loose_row = next(loose)
loose_row.append("dynamic")
print(loose_row, next(loose))

for offset in [3, 5]:
    it = concrete(offset)
    row = next(it)
    alias = row
    alias.append(offset + 2)
    print(row is alias, row, next(it))

# A caller's generator annotation is another concrete yield context.
annotated: Iterator[list[int]] = rows(8)
print(next(annotated))
print(list(rows(11)), list(concrete(13)))


def inferred_rows():
    yield [17]
    return ["separate return"]


def inferred_result() -> Iterator[list[int]]:
    result = yield from inferred_rows()
    print(result)


print(list(inferred_result()))
