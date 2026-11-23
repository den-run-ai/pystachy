# super().__init__(...) of a template hierarchy's class passes its arguments by position, by
# name and through the template's *args and keyword-only parameters, whose types decide the
# specialization it derives from (#962).
class Call:
    def __init__(self, name, *args, sep=", "):
        self.name = name
        self.args = args
        self.sep = sep

    def show(self) -> str:
        return self.name + "(" + self.sep.join([str(a) for a in self.args]) + ")"


class Pair(Call):
    def __init__(self, a: int, b: int) -> None:
        super().__init__("pair", a, b)


class Named(Call):
    def __init__(self) -> None:
        super().__init__(sep="; ", name="named")


class Spaced(Call):
    def __init__(self, x: str) -> None:
        super().__init__("spaced", x, x, sep=" ")


class Plain(Call):
    pass


print(Pair(1, 2).show(), Named().show(), Spaced("x").show())
print(Plain("plain", 3, 4).show(), Plain("one").show(), Plain("kw", 5, sep="|").show())
calls = [Call("c", 7, 8), Pair(5, 6), Plain("p", 9, 10)]
for c in calls:
    print(c.show(), len(c.args))
