# A tuple[A | B, ...] | None field holds objects of unrelated classes (mypyc's
# tuple[Dependency, ...] | None): its items dispatch methods on their classes and narrow with
# isinstance(), else branches too; a fixed tuple display converts item by item
class Capsule:
    def __init__(self, name: str) -> None:
        self.name = name

    def header(self) -> str:
        return self.name.split(".")[-1] + ".h"


class SourceDep:
    def __init__(self, path: str) -> None:
        self.path = path

    def header(self) -> str:
        return self.path.replace(".c", ".h")


Dependency = Capsule | SourceDep


class Primitive:
    def __init__(self, name: str, dependencies: tuple[Dependency, ...] | None = None) -> None:
        self.name = name
        self.dependencies = dependencies


def describe(p: Primitive) -> None:
    if p.dependencies is None:
        print(p.name, "none")
        return
    print(p.name, len(p.dependencies))
    for dep in p.dependencies:
        print(" ", dep.header())
        if isinstance(dep, Capsule):
            print("  capsule", dep.name)
        else:
            print("  source", dep.path)


LIBRT_STRINGS = Capsule("librt.strings")
describe(Primitive("bytes_writer", (LIBRT_STRINGS, SourceDep("bytes_extra_ops.c"))))
describe(Primitive("plain"))
describe(Primitive("empty", ()))
deps: tuple[Dependency, ...] = (SourceDep("a.c"),)
p = Primitive("later")
p.dependencies = deps
describe(p)
print(p.dependencies is deps, len(deps + (LIBRT_STRINGS,)))
