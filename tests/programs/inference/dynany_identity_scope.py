# Deliberately no dynamic-any directive: scopelib opts in, this module neither does nor is
# imported by one that does. Its own classes and functions keep their layouts and code
# (docs/dynamic-any.md#identity-scope); what it exchanges with scopelib (strings, Any values,
# a str -> Any callable) carries no number of its own, and Any values keep their objects.
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
print("counter", c.pos, c.n)
t = scopelib.table("5000")
print("table", scopelib.same(t["a"], t["b"]), scopelib.same(t["a"], t["c"]), scopelib.same(t["b"], t["a"]))
a = t["a"]
print("held", scopelib.same(a, t["a"]), scopelib.same(t["b"], a), scopelib.same(a, t["c"]))
print("callback", scopelib.call(lambda s: s + "!", t["s"]))
print("size", len(t), t["s"])
