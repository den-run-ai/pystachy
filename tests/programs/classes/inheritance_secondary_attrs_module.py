# A secondary base of another module that declares attributes: its values in fields, lists and
# dicts, its bound methods as Callables, and a class that derives from it alone beside one that
# combines it.
from typing import Callable

from mods.role_api import Options, PluginApi, describe


class Walker:
    def __init__(self) -> None:
        self.steps: list[str] = []


class Analyzer(Walker, PluginApi):
    def __init__(self, level: int) -> None:
        super().__init__()
        self.options = Options(level)
        self.names = {"a": 1}

    def fail(self, msg: str) -> None:
        self.steps.append(msg)


class Plain(PluginApi):
    def __init__(self) -> None:
        self.options = Options(9)
        self.names = {}

    def fail(self, msg: str) -> None:
        pass


class Holder:
    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def level(self) -> int:
        return self.api.options.level

    def bump(self) -> None:
        self.api.options = Options(self.api.options.level + 1)


def call(f: Callable[[], int]) -> int:
    return f()


a = Analyzer(3)
p = Plain()
print(describe(a), describe(p), a.level(), p.level())
h = Holder(a)
h.bump()
hp = Holder(p)
hp.bump()
print(h.level(), hp.level(), a.options.level, p.options.level)
apis: list[PluginApi] = [a, p]
print([call(x.level) for x in apis], [x.names for x in apis])
by: dict[str, PluginApi] = {"a": a, "p": p}
by["a"].names["z"] = 0
print(sorted(by["a"].names), by["p"].options.level)
