# Documented deviation: pprint has no id() to find a container that holds itself, which only a
# list or dict of a recursive value alias can do: the recursion limit stops it, with
# RecursionError. CPython writes <Recursion on list with id=...> in its place.
import pprint

type Tree = int | list[Tree]

inner: list[Tree] = [1]
inner.append(inner)
try:
    print(pprint.pformat(inner))
except RecursionError:
    print("RecursionError")
flat: list[Tree] = [1, [2, 3]]
print(pprint.pformat(flat), pprint.isrecursive(flat))
