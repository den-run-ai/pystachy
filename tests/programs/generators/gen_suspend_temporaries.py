# Each iterator keeps its own nested loop bounds and collection between yields.
from collections.abc import Iterator


def values(rows: list[list[int]], bias: int) -> Iterator[float]:
    for row in rows:
        for n in range(len(row)):
            yield row[n] + bias + 0.5
            if n % 2 == 0:
                yield -row[n] + bias + 0.25


rows = [[2, 4], [], [8]]
left = values(rows, 0)
right = values([[10], [20, 30]], 100)
print(next(left), next(right))
rows[0][0] = 6
print(next(right), next(left))
print(list(left))
print(list(right))
