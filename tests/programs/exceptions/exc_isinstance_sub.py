# isinstance() in a condition, of an exception whose static type is an exception class (or a
# builtin exception) against another exception class of the program: decided at run time when
# the object may be of a class deriving from the static type, or the static type derives from
# the class tested.
class A(Exception):
    pass


class B(A):
    pass


class C(Exception):
    pass


a: A = B()
if isinstance(a, B):
    print("a is a B")
if not isinstance(a, C):
    print("a is no C")
b = B()
if isinstance(b, A):
    print("b is an A")
print("B" if isinstance(a, B) else "not B", "A" if isinstance(A(), B) else "not B")


def kind(x):
    if isinstance(x, B):
        return "B"
    return "other"


print(kind(a), kind(A()))
try:
    raise B(1)
except Exception as e:
    assert isinstance(e, A)
    print("asserted")
    if isinstance(e, B) and not isinstance(e, C):
        print("caught a B")
    while isinstance(e, KeyError):
        print("never")
