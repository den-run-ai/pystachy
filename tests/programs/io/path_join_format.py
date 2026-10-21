# os.path.join() joins as posixpath.join does, and format(v, spec) is the f-string field {v:spec}
import os
import os.path
from os.path import join

print(os.path.join("a", "b"), os.path.join("a/", "b"), os.path.join("a", "/b", "c"), os.path.join("", "b"), os.path.join("a", ""))
print(os.path.join("a"), join("x", "y", "", "z"), os.path.join("/", "usr", "lib/"), os.path.join("a", "b/", "/", "c"))


class C:
    def __format__(self, spec: str) -> str:
        return "C[" + spec + "]"


class D:
    def __str__(self) -> str:
        return "d"


sp = ".1f"
print(format(4.0, ".1f"), format(3), format("a", ">3"), format(4.25, sp), format(C()), format(C(), "x"), format(D()), format(True, "d"), format(None), format(12, ","))
