# functools.total_ordering of a StrEnum: str's four ordering methods are the class's too, so
# CPython's decorator adds none. Only > runs the class's own method, which compares lengths;
# sorted() compares with str's <.
from enum import StrEnum
from functools import total_ordering


@total_ordering
class Size(StrEnum):
    S = "small"
    M = "md"
    L = "largest"

    def __gt__(self, other: "Size") -> bool:
        return len(self.value) > len(other.value)


print(Size.S < Size.M, Size.S <= Size.M, Size.S > Size.M, Size.S >= Size.M)
print(Size.M < Size.L, Size.M <= Size.L, Size.M > Size.L, Size.M >= Size.L)
print(sorted([Size.L, Size.S, Size.M]), max(Size.S, Size.L))
