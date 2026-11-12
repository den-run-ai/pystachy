# itertools.combinations() yields tuples of r items, a length the program knows only as it runs:
# runtime-length tuples, which hold objects too; permutations(), combinations_with_replacement(),
# product(..., repeat=n) and batched() too
from itertools import batched, combinations, combinations_with_replacement, permutations, product


class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"Point({self.x})"


points = [Point(1), Point(2), Point(3)]
print(len(list(combinations(points, 2))))
for pair in combinations(points, 2):
    print(pair, pair[0].x + pair[1].x)
print(list(permutations(points[:2])))
print(list(combinations_with_replacement(points[:2], 2)))
print(list(product(points[:2], repeat=2)))
print(list(batched(points, 2)))
