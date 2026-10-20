# Importing a subclass also resolves its ancestor and inherits fields inferred from __init__.
from mods.inheritance import Base as Root, Derived, Owner


class Local(Derived):
    def value(self) -> int:
        return super().value() + 100


def report(obj: Root) -> None:
    print(obj.n, obj.value(), obj.twice(), isinstance(obj, Root), isinstance(obj, Derived))


report(Root(1))
report(Derived(2))
report(Local(4))
print(Owner().child.n, Owner().value())
