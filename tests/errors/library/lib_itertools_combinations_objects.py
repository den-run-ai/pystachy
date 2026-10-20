# error: runtime-length tuple elements must be int, float, bool, str or their optional types (compiling itertools._combinations(
# itertools.combinations() yields tuples of r items, a length the program knows only as it runs;
# such a tuple holds ints, floats, bools, strs or their optional types (lib/compatibility.md),
# not objects; permutations(), combinations_with_replacement() and product(..., repeat=n) too
from itertools import combinations


class Point:
    def __init__(self, x: int) -> None:
        self.x = x


print(len(list(combinations([Point(1), Point(2), Point(3)], 2))))
