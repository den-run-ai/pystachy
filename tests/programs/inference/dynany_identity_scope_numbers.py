# Deliberately no dynamic-any directive: this module's numbers cross into scopelib, which opts in
# and keeps them as Any values: a binding passed twice is one object there
# (docs/dynamic-any.md#identity-scope).
import scopelib


def twice(x: int) -> None:
    scopelib.keep(x)
    scopelib.keep(x)


v = int("3000")
w = v
scopelib.keep(v)
scopelib.keep(w)
print("module", scopelib.kept_same())
scopelib.kept.clear()
twice(int("4000"))
print("function", scopelib.kept_same())
