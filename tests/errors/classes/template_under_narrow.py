# error: 'Base' object has no method 'show' (it is T's, a class template: isinstance(x, T) tests every specialization of T but cannot narrow a Base to one type; define show on Base, or annotate the parameters of T.__init__ so that T is one class)
# isinstance(x, T) of a value of an ordinary class holds for an object of any specialization of the
# class template T under it (#962), but the value keeps its class: T's own method is no Base's.
class Base:
    def __init__(self) -> None:
        self.n = 1


class T(Base):
    def __init__(self, item):
        super().__init__()
        self.item = item

    def show(self) -> str:
        return "T " + repr(self.item)


def main() -> None:
    xs: list[Base] = [Base(), T("s"), T(2)]
    for x in xs:
        if isinstance(x, T):
            print(x.show(), x.n)
        else:
            print("base", x.n)


main()
