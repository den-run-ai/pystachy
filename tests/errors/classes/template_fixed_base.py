# error: template_fixed_base.py:13: error: inheritance with generic class templates is not supported: annotate __init__ parameters with concrete types (not Any or object)
# A class template whose base is an ordinary class (logging's Logger, which derives from Filterer)
# is not supported (#962): its specializations would join the hierarchy of a class whose objects
# compiled code may already dispatch on.
class Base:
    def __init__(self) -> None:
        self.filters: list[str] = []

    def hello(self) -> str:
        return "hi " + str(len(self.filters))


class T(Base):
    def __init__(self, name, level=0):
        super().__init__()
        self.name = name
        self.level = level


t = T("a", 3)
print(t.name, t.level, t.hello())
