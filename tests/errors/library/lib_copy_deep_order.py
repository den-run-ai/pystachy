# error: copy.deepcopy() of a A object is not supported: copying its attributes may run a __deepcopy__(), __hash__() or __eq__() method, which CPython runs in its __dict__'s order
# A hook's turn depends on the __dict__'s order, here an assignment in a branch of __init__'s
import copy
import sys


class Hook:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def __deepcopy__(self, memo) -> "Hook":
        print("hook", self.tag)
        return Hook(self.tag)


class A:
    def __init__(self) -> None:
        if len(sys.argv) > 1:
            self.second = Hook("second")
            self.first = Hook("first")
        else:
            self.first = Hook("first")
            self.second = Hook("second")


c = copy.deepcopy(A())
print(c.first.tag, c.second.tag)
