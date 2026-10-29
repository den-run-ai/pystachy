# Deliberately no dynamic-any directive: scopelib opts in, this module neither does nor is
# imported by one that does (docs/dynamic-any.md#identity-scope, #969). Counter keeps its
# two-word layout (.tbaa: no companion slots) and step() boxes nothing (.calls).
import scopelib


class Counter:
    def __init__(self) -> None:
        self.pos = 0
        self.n = 0

    def step(self, k: int) -> None:
        for i in range(k):
            self.pos = self.pos + i
            self.n += 1


c = Counter()
c.step(int("1000"))
print(c.pos, c.n, scopelib.same("a", "b"))
