# Dotted value patterns compare runtime values, including None in unrelated optional types.
# A hierarchy's None alternative must not share the never-equal class comparison arm.
class Node:
    pass


class Leaf(Node):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Leaf)


class Values:
    def __init__(self, n: str | None) -> None:
        self.n = n


def matches(o: Node | None, values: Values) -> bool:
    match o:
        case values.n:
            return True
        case _:
            return False


print(matches(None, Values(None)))
print(matches(Leaf(), Values(None)))
print(matches(None, Values("x")))
