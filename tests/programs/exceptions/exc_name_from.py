class I(ImportError):
    def __init__(self, mod: str) -> None:
        super().__init__("no " + mod, name_from="from-init")
        self.name_from: str = "x"


class M(ModuleNotFoundError):
    def __init__(self, mod: str) -> None:
        super().__init__("no " + mod, name_from="from-init")
        self.name_from: str = "y"


class Inherited(ImportError):
    pass


class ModuleInherited(ModuleNotFoundError):
    pass


def source() -> str:
    print("keyword evaluated")
    return "f"


i = I("m")
print(str(i), repr(i), i.name_from)
m = M("m")
print(str(m), repr(m), m.name_from)
print(repr(ImportError("msg", name="n", path="p", name_from=source())))
print(repr(ModuleNotFoundError("msg", name_from=None)))
print(repr(Inherited("msg", name_from="f")))
print(repr(ModuleInherited("msg", name_from="f")))
