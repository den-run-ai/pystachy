# error: overriding '_from_iterable' of 'Set' with another kind of method
# Set's _from_iterable is an instance method here (a class method that uses cls is compiled only for
# the class that defines it): a subclass that overrides it with a class method, as CPython's
# documentation suggests, is rejected rather than miscompiled
from collections.abc import Set


class Bits(Set):
    def __init__(self, n: int) -> None:
        self.n = n

    def __contains__(self, x: int) -> bool:
        return 0 <= x < 64 and (self.n >> x) & 1 == 1

    def __iter__(self):
        return iter([i for i in range(64) if (self.n >> i) & 1])

    def __len__(self) -> int:
        return len([i for i in range(64) if (self.n >> i) & 1])

    @classmethod
    def _from_iterable(cls, it):
        n = 0
        for i in it:
            n |= 1 << i
        return cls(n)


print(sorted(Bits(5) & Bits(6)))
