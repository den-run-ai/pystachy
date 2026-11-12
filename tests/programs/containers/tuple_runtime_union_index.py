# An item of a tuple[A | B, ...] read by index (xs[i], also negative and out of range) narrows with
# isinstance(), else branch too, as the items a loop over it takes do
import sys


class Capsule:
    def __init__(self, name: str) -> None:
        self.name = name


class SourceDep:
    def __init__(self, path: str) -> None:
        self.path = path


def describe(deps: tuple[Capsule | SourceDep, ...], i: int) -> str:
    dep = deps[i]
    if isinstance(dep, Capsule):
        return "capsule " + dep.name
    return "source " + dep.path


deps: tuple[Capsule | SourceDep, ...] = (Capsule("librt.strings"), SourceDep("bytes_extra_ops.c"))
for i in range(len(deps)):
    print(describe(deps, i))
print(describe(deps, -1), "|", describe(deps, len(sys.argv) - 3))
try:
    describe(deps, 5)
except IndexError as e:
    print("IndexError", e)
