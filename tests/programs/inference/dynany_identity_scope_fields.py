# Deliberately no dynamic-any directive: an object of this module's class crosses into scopelib,
# which opts in and reads its fields through Any, both operand orders: they keep their objects
# (docs/dynamic-any.md#identity-scope).
import scopelib


class Box:
    def __init__(self, n: int) -> None:
        self.n = n
        self.m = self.n
        self.k = int(str(n))


b = Box(int("1000"))
print("fields", scopelib.fields(b, b.n))
b.n = b.n + 1
print("rebound", scopelib.fields(b, b.n))
