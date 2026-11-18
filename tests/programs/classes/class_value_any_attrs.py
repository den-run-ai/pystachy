# Class attributes, class methods and static methods through a class object that may be any
# class's (type[object]): the class the value is gives its own, where the classes that have
# the name agree on one type. A class without the name, a builtin class and NoneType raise
# CPython's AttributeError, before a call's arguments are evaluated.
class Base:
    limit = 1


class A(Base):
    tag = "a"
    limit = 3

    @classmethod
    def make(cls) -> str:
        return "made " + cls.__name__

    @staticmethod
    def kind() -> str:
        return "A-kind"


class B(A):
    tag = "b"


class P:
    tag = "p"

    @classmethod
    def make(cls) -> str:
        return "P made " + cls.__name__

    @staticmethod
    def scale(n: int) -> int:
        return n * 2


class Q:
    pass


def show(k: type) -> None:
    try:
        print(k.__name__, k.tag)
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print(k.limit)
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print(k.make())
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print(k.kind())
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print(k.scale(4))
    except AttributeError as e:
        print("AttributeError:", e)


kinds: list[type] = [Base, A, B, P, Q, int, str, type(None)]
for k in kinds:
    show(k)
registry: dict[str, type] = {"a": A, "p": P}
print(registry["a"].tag, registry["p"].make(), [k.tag for k in registry.values()])
