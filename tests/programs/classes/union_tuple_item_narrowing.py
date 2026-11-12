# Items that a loop reads from a tuple whose items are all of one union of classes narrow with
# isinstance(), in its else branch too: the IR check proves their members from the tuple's own
# item type (the loop reads its slots through a machine address, as it reads a list's items
# through list.get)
class Capsule:
    def __init__(self, name: str) -> None:
        self.name = name

    def header(self) -> str:
        return self.name + ".h"


class SourceDep:
    def __init__(self, path: str) -> None:
        self.path = path

    def header(self) -> str:
        return self.path.replace(".c", ".h")


class HeaderDep:
    def __init__(self, path: str) -> None:
        self.path = path

    def header(self) -> str:
        return self.path


def describe(deps: tuple[Capsule | SourceDep, Capsule | SourceDep]) -> list[str]:
    out: list[str] = []
    for dep in deps:
        out.append(dep.header())
        if isinstance(dep, Capsule):
            out.append("capsule " + dep.name)
        else:
            out.append("source " + dep.path)
    return out


def kinds(deps: tuple[Capsule | SourceDep | HeaderDep, Capsule | SourceDep | HeaderDep, Capsule | SourceDep | HeaderDep]) -> list[str]:
    out: list[str] = []
    for dep in deps:
        if isinstance(dep, Capsule):
            out.append("capsule " + dep.name)
        elif isinstance(dep, SourceDep):
            out.append("source " + dep.path)
        else:
            out.append("header " + dep.path)
    return out


class Holder:
    def __init__(self, deps: tuple[Capsule | SourceDep, Capsule | SourceDep] | None) -> None:
        self.deps = deps


def paths(h: Holder) -> list[str]:
    # (a tuple that may be None: its items read where it is not)
    out: list[str] = []
    if h.deps is not None:
        for dep in h.deps:
            if isinstance(dep, Capsule):
                out.append("capsule " + dep.name)
            else:
                out.append("source " + dep.path)
    return out


print(describe((Capsule("librt.strings"), SourceDep("bytes_extra_ops.c"))))
print(describe((SourceDep("a.c"), SourceDep("b.c"))))
print(kinds((HeaderDep("x.h"), Capsule("librt.vecs"), SourceDep("y.c"))))
print(paths(Holder((SourceDep("z.c"), Capsule("librt.time")))), paths(Holder(None)))
