# copy.deepcopy() of an object whose __deepcopy__() hook gives the original an attribute it lacked:
# CPython's copy iterates the original's __dict__, which then changed size, and raises RuntimeError;
# with the attribute already there, the copy gets the value the hook gave it
import copy


class Hook:
    def __init__(self) -> None:
        self.owner: "A | None" = None

    def __deepcopy__(self, memo) -> "Hook":
        if self.owner is not None:
            self.owner.extra = 5
        return Hook()


class A:
    def __init__(self, flag: bool) -> None:
        self.first = Hook()
        if flag:
            self.extra = 1


for flag in [False, True]:
    a = A(flag)
    a.first.owner = a
    try:
        c = copy.deepcopy(a)
        print(flag, "copied", c.extra)
    except RuntimeError as e:
        print(flag, "RuntimeError:", e)
    print(flag, a.extra)
