# isinstance()'s second argument is built before the test: a class whose class statement has not
# run yet raises NameError there, also in a tuple or union with a class that matches, and where
# the static types decide the test (if, while, assert, a conditional expression, and, or, not);
# an and/or that stops before the test reads nothing.
class A:
    pass


class E(Exception):
    pass


def side() -> A:
    print("side")
    return A()


def plain(a: A) -> bool:
    return isinstance(a, Later)


def folded(a: A) -> str:
    if isinstance(a, Later):
        return "Later"
    return "not Later"


def in_tuple(a: A) -> bool:
    return isinstance(a, (A, Later))


def in_union(a: A) -> bool:
    return isinstance(a, A | Later)


def ternary(a: A) -> str:
    return "yes" if not isinstance(a, Later) else "no"


def stops(a: A) -> bool:
    return isinstance(a, A) or isinstance(a, Later)


def reaches(a: A) -> bool:
    return isinstance(a, A) and isinstance(a, Later)


def first(a: A) -> bool:
    return isinstance(a, Later) and len(str(a)) > 0


def asserted(a: A) -> str:
    assert not isinstance(a, Later)
    return "asserted"


def looped(a: A) -> str:
    while isinstance(a, Later):
        print("loop")
    return "looped"


def evaluated_first() -> bool:
    return isinstance(side(), Later)


def template(v):
    if isinstance(v, Later):
        return "Later"
    return str(v)


def caught(e: E) -> bool:
    return isinstance(e, LateError)


def optional(x: "Later | None") -> str:
    if isinstance(x, Later):
        return "Later"
    return "None"


class M:
    def method(self, a: A) -> bool:
        return isinstance(a, (Later, A))


def run() -> None:
    a = A()
    try:
        print("plain", plain(a))
    except NameError as e:
        print("plain:", e)
    try:
        print("folded", folded(a))
    except NameError as e:
        print("folded:", e)
    try:
        print("in_tuple", in_tuple(a))
    except NameError as e:
        print("in_tuple:", e)
    try:
        print("in_union", in_union(a))
    except NameError as e:
        print("in_union:", e)
    try:
        print("ternary", ternary(a))
    except NameError as e:
        print("ternary:", e)
    try:
        print("stops", stops(a))
    except NameError as e:
        print("stops:", e)
    try:
        print("reaches", reaches(a))
    except NameError as e:
        print("reaches:", e)
    try:
        print("first", first(a))
    except NameError as e:
        print("first:", e)
    try:
        print(asserted(a))
    except NameError as e:
        print("asserted:", e)
    try:
        print(looped(a))
    except NameError as e:
        print("looped:", e)
    try:
        print("evaluated_first", evaluated_first())
    except NameError as e:
        print("evaluated_first:", e)
    try:
        print("template", template(1), template("s"))
    except NameError as e:
        print("template:", e)
    try:
        print("caught", caught(E("e")))
    except NameError as e:
        print("caught:", e)
    try:
        print("optional", optional(None))
    except NameError as e:
        print("optional:", e)
    try:
        print("method", M().method(a))
    except NameError as e:
        print("method:", e)


try:
    print(isinstance(A(), Later))
except NameError as e:
    print("module:", e)
run()


class Later:
    pass


class LateError(E):
    pass


run()
print(isinstance(A(), Later), isinstance(Later(), (A, Later)), isinstance(LateError("x"), E), optional(Later()))
