# pystachy: dynamic-any
# formatting Any values: %, str.format, f-string specs, join of str()
from typing import Any

vals: list[Any] = [1, 2.5, "s", None, [1, "a"]]
print("%s|%r|%s" % (vals[0], vals[2], vals[4]))
print("{} and {}".format(vals[1], vals[3]))
print(f"{vals[1]:8.3f}|{vals[0]:>5}|{vals[2]!r}")
print(", ".join(str(v) for v in vals))
