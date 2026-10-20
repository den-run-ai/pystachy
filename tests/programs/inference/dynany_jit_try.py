# pystachy: dynamic-any
# A try statement around a method call of an Any value catches what the call raises, also in a
# JIT run that has a function that only raises (here callv.1's, a call of a value that no boxed
# function answers): LLVM put such cold functions in .text.unlikely, where lli's ORC lost the
# landing pads that its inliner had moved into main.
from typing import Any

d: Any = {"a": 1}
try:
    d.pop("zz")
except KeyError as err:
    print("caught pop:", err)
arg: Any = "a"
print(d.get(arg))
xs: Any = [1]
try:
    xs.index(5)
except ValueError as err:
    print("caught index:", err)
print("end")
