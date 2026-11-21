# error: copy.copy() of an object of Stack, a class that derives from list, is not supported yet
import copy


class Stack(list[int]):
    def __init__(self) -> None:
        self.name = "s"


s = Stack()
t = copy.copy(s)
print(t)
