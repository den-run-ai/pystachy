# A secondary base may declare attributes by annotation, as mypy's plugin interfaces do
# (CheckerPluginInterface: msg, options, path). The class that combines it holds them; a value
# of the base's type reads and stores them by the object's own class, and so do the base's methods.
from abc import abstractmethod


class Options:
    def __init__(self, strict: bool) -> None:
        self.strict = strict


class Api:
    options: Options
    path: str
    depth: int
    seen: list[str]
    last: str | None

    @abstractmethod
    def fail(self, msg: str) -> None:
        raise NotImplementedError

    def strict(self) -> bool:
        return self.options.strict

    def enter(self) -> int:
        self.depth += 1
        self.seen.append(self.path)
        self.last = self.path
        return self.depth


class Flags:
    recurse: bool
    depth: int


class Visitor:
    def __init__(self) -> None:
        self.visits = 0

    def visit(self) -> str:
        self.visits += 1
        return "v" + str(self.visits)


class Checker(Visitor, Api, Flags):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.options = Options(True)
        self.path = path
        self.depth = 0
        self.seen = []
        self.last = None
        self.recurse = False
        self.errors: list[str] = []

    def fail(self, msg: str) -> None:
        self.errors.append(self.path + ": " + msg)


class Sub(Checker):
    def __init__(self) -> None:
        super().__init__("sub.py")
        self.extra = 7

    def fail(self, msg: str) -> None:
        self.errors.append("sub: " + msg)


class Analyzer(Visitor, Flags):
    def __init__(self) -> None:
        super().__init__()
        self.name = "an"
        self.recurse = True
        self.depth = -1


class Lazy(Visitor, Api):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0

    def fail(self, msg: str) -> None:
        pass


def use(api: Api) -> bool:
    api.fail("x")
    api.path = api.path + "!"
    api.depth += 10
    api.seen.append("u")
    return api.options.strict


def flip(f: Flags) -> list[bool]:
    out = [f.recurse]
    f.recurse = not f.recurse
    out.append(f.recurse)
    f.depth *= 2
    return out


def path_of(api: Api | None) -> str:
    try:
        return api.path
    except AttributeError as e:
        return "error: " + str(e)


c = Checker("m.py")
s = Sub()
a = Analyzer()
print(use(c), c.errors, c.path, c.strict(), c.visit(), c.depth, c.seen, c.last)
print(c.enter(), c.depth, c.seen, c.last)
print(use(s), s.errors, s.path, s.extra, s.enter(), s.last)
print(flip(c), flip(s), flip(a), c.recurse, a.recurse, a.name, c.depth, a.depth)
print(path_of(c), path_of(None), path_of(Lazy()))
apis: list[Api] = [c, s]
print([x.path for x in apis], [x.enter() for x in apis], sum([x.depth for x in apis]))
print(isinstance(c, Api), isinstance(a, Api), isinstance(a, Flags))
print(getattr(c, "path"), hasattr(c, "path"), hasattr(Lazy(), "path"), getattr(Lazy(), "path", "none"))
# an object of the base itself has the attributes its own code stores
bare = Api()
print(path_of(bare))
bare.path = "own"
bare.depth = 1
print(path_of(bare), bare.depth)
