# A tuple's in, count() and index() compile a call of __eq__ for each pair of classes the item
# and the value sought may be of, None included. A template __eq__ (other: object, or no
# annotation) whose body does not compile for an operand declines that pair rather than making
# the program a compile error, as before the search dispatched on classes (#409)


class A:
    def __eq__(self, other: object) -> bool:
        return other.missing()


class B:
    pass


class U:
    def __eq__(self, other):
        return other.missing()


def search(x: A | B, y: A | B) -> bool:
    return x in (y,)


def in_class(x: A | B, y: B) -> bool:
    return x in (y,)


def class_in(x: B, y: A | B) -> bool:
    return x in (y,)


def count(x: A | B, y: A | B) -> int:
    return (y, x).count(x)


def index(x: A | B, y: A | B) -> int:
    return (y, x).index(x)


def untyped(x: U | B, y: U | B) -> bool:
    return x in (y,)


print(search(B(), B()))
b = B()
print(search(b, b), in_class(B(), B()), in_class(b, b), class_in(B(), B()), class_in(b, b))
print(count(B(), B()), count(b, b), index(B(), B()), index(b, b))
print(untyped(B(), B()), untyped(b, b))
