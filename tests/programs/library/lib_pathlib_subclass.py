# Subclasses of the path classes, with and without an __init__ of their own; paths made from
# strs and paths together; and an argument that is neither, which raises when the call runs.
from pathlib import Path, PurePath, PurePosixPath


class Tagged(PurePosixPath):
    def describe(self) -> str:
        return "tagged:" + str(self)


class Rooted(Path):
    def __init__(self, name: str) -> None:
        super().__init__("/srv", name)
        self.label: str = name.upper()


def show(p: PurePath) -> str:
    return type(p).__name__ + ":" + str(p) + ":" + p.name


t = Tagged("a", "b")
print(t.describe(), t.name, isinstance(t, PurePath), type(t).__name__, show(t))
r = Rooted("data")
print(r, r.label, r.parent, isinstance(r, Path), r.is_absolute(), show(r))
print(show(Path("x", PurePath("y", "z"))), show(PurePath(Path("/a"), "b")))
print(Path("a") == PurePath("a"), PurePath("a") == PurePosixPath("a"), len({PurePath("a"), PurePath("a/")}))
print(PurePath("/a/b/c").relative_to(PurePath("/a")), PurePath("/a/b").is_relative_to(Path("/a")), PurePath("a/b.py").match("*.py"))
try:
    PurePath(1)
except TypeError as e:
    print(e)
try:
    Path("a", None)
except TypeError as e:
    print(e)
try:
    PurePath("a", 2.5, "c")
except TypeError as e:
    print(e)
try:
    PurePath("a").relative_to(7)
except TypeError as e:
    print(e)
for p in PurePath("/a/b/c").parents:
    print(show(p))
print([show(q) for q in Path("/a/b").parents], len(Path("/x/y/z").parents))
