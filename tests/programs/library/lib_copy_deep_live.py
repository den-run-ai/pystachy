# copy.deepcopy() of an object copies its __dict__ as CPython does: in its insertion order, each
# attribute read as the copy reaches it, so that a __deepcopy__() of an earlier attribute that
# changes a later one of the original gives the copy the new value; an attribute that __init__
# assigns before calling its base's __init__ comes first
import copy


class Hook:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.owner: "A | None" = None

    def __deepcopy__(self, memo) -> "Hook":
        print("hook", self.tag)
        if self.owner is not None:
            self.owner.later = 9
        return Hook(self.tag)


class A:
    def __init__(self) -> None:
        self.first = Hook("first")
        self.later = 1
        self.items = [Hook("in list")]


a = A()
a.first.owner = a
c = copy.deepcopy(a)
print(a.later, c.later, c.first.tag, c.items[0].tag)


class Base:
    def __init__(self) -> None:
        self.base_field = Hook("base")


class Derived(Base):
    def __init__(self) -> None:
        self.derived_field = Hook("derived")
        super().__init__()


d = copy.deepcopy(Derived())
print(d.derived_field.tag, d.base_field.tag)
