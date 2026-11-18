# A tuple search over objects of a union of classes, one of whose __eq__ is a template that
# compiles for no operand, which the program never compares: it runs as before the search
# dispatched on classes, rather than becoming a compile error (#409)


class A:
    def __eq__(self, other: object) -> bool:
        return other.missing()


class B:
    pass


def search(x: A | B, y: A | B) -> bool:
    return x in (y,)


print(search(B(), B()))
