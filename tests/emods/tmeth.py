# a class whose method broken() is a template that no argument type compiles
class Acc:
    def __init__(self, start: int) -> None:
        self.total = start

    def add(self, x):
        self.total += x
        return self

    def describe(self, label, sep=": "):
        return label + sep + str(self.total)

    def each(self, *xs, **opts):
        return [self.total + x for x in xs], sorted(opts)

    def broken(self, x):
        return x.no_such_thing()


class Oops(ValueError):
    def detail(self, extra):
        return str(self) + "/" + str(extra)


class Worse(Oops):
    pass
