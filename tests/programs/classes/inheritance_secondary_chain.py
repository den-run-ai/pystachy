# A secondary base may derive from another (an interface that extends one, as mypy's
# TypeCheckerSharedApi(CheckerPluginInterface)), and declare properties, abstract or not. A value
# of either interface's type reads their attributes and properties by the object's own class.
from abc import abstractmethod


class Options:
    def __init__(self, level: int) -> None:
        self.level = level


class Core:
    options: Options
    name: str

    @property
    def level(self) -> int:
        return self.options.level

    @property
    @abstractmethod
    def final(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def fail(self, msg: str) -> str:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name + ":" + str(self.level) + ":" + str(self.final)


class Shared(Core):
    scope: list[str]

    def fail(self, msg: str) -> str:
        self.scope.append(msg)
        return "shared " + msg

    def push(self, s: str) -> int:
        self.scope.append(s)
        return len(self.scope)


class Wide(Shared):
    extra: int


class Visitor:
    def __init__(self) -> None:
        self.visits = 0


class Checker(Visitor, Shared):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.options = Options(2)
        self.name = name
        self.scope = []

    @property
    def final(self) -> bool:
        return len(self.scope) > 1


class Analyzer(Visitor, Wide):
    def __init__(self) -> None:
        self.before = "b"
        super().__init__()
        self.options = Options(5)
        self.name = "an"
        self.scope = ["s"]
        self.extra = 9

    @property
    def final(self) -> bool:
        return True

    def fail(self, msg: str) -> str:
        return "analyzer " + msg


class Plain(Shared):
    def __init__(self) -> None:
        self.options = Options(1)
        self.name = "plain"
        self.scope = []

    @property
    def final(self) -> bool:
        return False


def core(c: Core) -> str:
    c.name = c.name + "'"
    return c.describe() + " " + c.fail("f") + " " + str(c.level)


def shared(s: Shared) -> str:
    n = s.push("p")
    s.options = Options(s.options.level * 10)
    return str(n) + s.name + str(s.level) + str(s.final) + ",".join(s.scope)


def kind(c: Core) -> str:
    if isinstance(c, Wide):
        c.extra += 1
        return "wide" + str(c.extra)
    if isinstance(c, Shared):
        return "shared" + str(len(c.scope))
    return "core"


xs: list[Core] = [Checker("ch"), Analyzer(), Plain()]
print([core(x) for x in xs])
ys: list[Shared] = [Checker("c2"), Analyzer(), Plain()]
print([shared(y) for y in ys])
print([kind(x) for x in xs], [isinstance(x, Shared) for x in xs], [isinstance(x, Visitor) for x in xs])
