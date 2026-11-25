# Copies keep the Counter subclass, its overrides and its independent mapping (#1741).
from collections import Counter


class Counts(Counter):
    def total(self) -> int:
        return 99


class DeepCounts(Counts):
    pass


for original in [Counter('abb'), Counts('abb'), DeepCounts('abb')]:
    copied = original.copy()
    print(type(original).__name__, type(copied).__name__, isinstance(copied, Counts))
    print(copied.total(), repr(copied), copied is original, copied == original)
    copied['b'] += 3
    print(original['b'], copied['b'])

for original in [Counts(''), Counts('a')]:
    print(repr(original.copy()))
