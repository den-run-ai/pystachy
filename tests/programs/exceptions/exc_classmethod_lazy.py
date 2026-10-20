# Inherited methods are copied only when compiled. Their flow flags and cls binding must
# belong to the subclass, while literal defaults and Self annotations keep their meaning.
from typing import Self


class Base(Exception):
    tag = "base"

    @classmethod
    def make(klass, text: str = "default") -> Self:
        return klass(text + "/" + klass.tag)

    @classmethod
    def read(klass, ready: bool) -> str:
        if ready:
            local = klass.__name__
        return local + suffix


def before() -> None:
    print("before subclasses")


before()


class Child(Base):
    tag = "child"


class Leaf(Child):
    tag = "leaf"


# Body checks run separately for each compiled method; a sibling must not inherit the
# first method's renamed names or definite-assignment annotations.
for ready in [False, True]:
    try:
        print(Child.read(ready))
    except UnboundLocalError:
        print("child local unbound")
    except NameError:
        print("child global unbound")
    try:
        print(Leaf.read(ready))
    except UnboundLocalError:
        print("leaf local unbound")
    except NameError:
        print("leaf global unbound")
suffix = "!"
print(Base.read(True), Child.read(True), Leaf.read(True))
for value in [Base.make(), Child.make(), Leaf.make("custom")]:
    print(type(value).__name__, str(value))
print(Child.make().tag, Leaf.make().tag)
