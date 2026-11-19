# mypy's checker interfaces: abstract properties and attributes in an interface and in the one
# that extends it, implemented by the class that combines them with a visitor.
from abc import abstractmethod


class Options:
    def __init__(self, strict: bool) -> None:
        self.strict = strict


class PluginApi:
    options: Options
    path: str

    @property
    @abstractmethod
    def context(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def fail(self, msg: str) -> None:
        raise NotImplementedError


class SharedApi(PluginApi):
    scope: list[str]
    waiting: bool

    @property
    @abstractmethod
    def checker(self) -> "Checker":
        raise NotImplementedError

    @abstractmethod
    def accept(self, name: str) -> str:
        raise NotImplementedError


class Visitor:
    def __init__(self) -> None:
        self.visits = 0


class Checker(Visitor, SharedApi):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.options = Options(True)
        self.path = path
        self.scope = [path]
        self.waiting = False
        self.errors: list[str] = []

    @property
    def context(self) -> list[str]:
        return self.scope + ["ctx"]

    @property
    def checker(self) -> "Checker":
        return self

    def fail(self, msg: str) -> None:
        self.errors.append(self.path + ": " + msg)

    def accept(self, name: str) -> str:
        self.scope.append(name)
        return name.upper()


def plugin(api: PluginApi) -> str:
    api.fail("p")
    return api.path + str(api.options.strict) + ",".join(api.context)


def shared(api: SharedApi) -> str:
    api.fail("s")
    api.waiting = True
    return api.accept("x") + api.path + ",".join(api.context) + str(len(api.scope)) + api.checker.path


c = Checker("m.py")
print(plugin(c), shared(c), c.errors, c.waiting, isinstance(c, PluginApi), isinstance(c, SharedApi))
