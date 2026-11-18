from mods.super_own_names import Imported as Renamed


class Error(Exception):
    def text(self) -> str:
        return super().__str__()

    def representation(self) -> str:
        return super(Error, self).__repr__()


class Base:
    def __str__(self) -> str:
        print("base str")
        return "text"

    def __repr__(self) -> str:
        print("base repr")
        return "representation"


class Child(Base):
    def text(self) -> str:
        return super().__str__()

    def representation(self) -> str:
        return super(Child, self).__repr__()

    def reassigned(self) -> str:
        self = None
        return super().__str__()


class Leaf(Child):
    def ancestor_text(self) -> str:
        return super(Child, self).__str__()

    def ancestor_repr(self) -> str:
        return super(Child, self).__repr__()


for present in [False, True]:
    error: Error | None = Error("message") if present else None
    print(Error.text(error), Error.representation(error))
    child: Child | None = Child() if present else None
    print(Child.text(child), Child.representation(child))
    leaf: Leaf | None = Leaf() if present else None
    print(Leaf.ancestor_text(leaf), Leaf.ancestor_repr(leaf))
    imported: Renamed | None = Renamed("imported") if present else None
    print(Renamed.text(imported), Renamed.representation(imported))

print(Child().reassigned())
