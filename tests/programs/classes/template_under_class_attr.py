# A class attribute that only the ordinary base binds, read through the name of a class template
# under it (#962), as through an ordinary subclass's: the base's, with its current value, and for a
# mutable one the same object (assigning it through the template's name is an error, as through an
# ordinary subclass's: tests/errors/classes/template_under_class_store.py).
class Base:
    unit = "cm"
    registry: list[str] = []

    def __init__(self) -> None:
        self.n = 0


class T(Base):
    def __init__(self, v):
        super().__init__()
        self.v = v


t = T(3)
print(T.unit, t.unit, Base.unit, T.registry is Base.registry)
Base.unit = "mm"
T.registry.append("x")
print(T.unit, t.unit, T("s").unit, Base.registry, t.registry)
