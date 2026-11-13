# union descriptors whose member ends in an empty tuple's T0, a count read as one character, beside
# members whose class id ends their descriptor (O<id>, which a '.' ends before the next tag)
class C:
    def __repr__(self) -> str:
        return "C()"


def show(x: list[tuple[()]] | str) -> None:
    print(repr(x), [x])


def mixed(x: list[tuple[()]] | list[C] | int) -> None:
    print(repr(x), [x])


show("hello")
show([()])
mixed([()])
mixed([C()])
mixed(3)
