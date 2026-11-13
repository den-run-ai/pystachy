# a union whose members hold objects of different classes inside containers: runtime.c's descriptor
# of each member ends its class's id with a '.', so the next member's tag is not read as more of
# the id (the list[C] value printed as list[D]'s)
class C:
    def __repr__(self) -> str:
        return "C()"


class D:
    def __repr__(self) -> str:
        return "D()"


def show(x: list[C] | list[D] | int) -> None:
    print(repr(x), [x], x)


show(3)
show([C()])
show([D()])
