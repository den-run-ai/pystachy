# copy.deepcopy() of an object of __slots__ copies the slots' values as they were when the copy
# began, as CPython's copyreg state of slots is a dict made first: a __deepcopy__() that changes a
# later slot of the original leaves the copy's; the derived class's slots come first
import copy


class Hook:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.owner: "S | None" = None

    def __deepcopy__(self, memo) -> "Hook":
        print("hook", self.tag)
        if self.owner is not None:
            self.owner.later = 9
        return Hook(self.tag)


class Base:
    __slots__ = ("base_hook",)

    def __init__(self) -> None:
        self.base_hook = Hook("base")


class S(Base):
    __slots__ = ("first", "later")

    def __init__(self) -> None:
        super().__init__()
        self.first = Hook("first")
        self.later = 1


s = S()
s.first.owner = s
c = copy.deepcopy(s)
print(s.later, c.later, c.first.tag, c.base_hook.tag)
