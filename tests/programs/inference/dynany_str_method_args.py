# pystachy: dynamic-any
# A str's split(), rsplit(), strip(), lstrip() and rstrip() through Any take None as CPython's
# do (whitespace), and startswith() and endswith() a tuple of str affixes, tried in turn, with
# CPython's TypeError for an item that is no str where the search reaches it.
from typing import Any

s: Any = " a,b,,c "
none: Any = None
one: Any = 1
print(s.split(none), s.split(none, one), s.rsplit(none, one), s.strip(none), s.lstrip(none), s.rstrip(none))
print(s.split(","), s.strip(" a"), s.rsplit(",", one))
prefixes: Any = (" a", "x")
suffixes: Any = ("x", "c ")
empty: Any = ()
print(s.startswith(prefixes), s.endswith(suffixes), s.startswith(prefixes, 1), s.endswith(suffixes, 0, 3))
print(s.startswith(empty), s.startswith(" a"), s.endswith(("a",)), s.startswith(("x", " a,b")))
early: Any = (" a", 1)
print(s.startswith(early))
for bad in [(1, " a"), ("x", None)]:
    late: Any = bad
    try:
        print(s.startswith(late))
    except TypeError as error:
        print("TypeError", error)
    try:
        print(s.endswith(late))
    except TypeError as error:
        print("TypeError", error)
