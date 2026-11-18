# A call is import_module()'s only where its name binds importlib's function there: a parameter
# or a local variable named as the module's alias of importlib is another object, whose method
# import_module() the call runs.
import importlib as il


class Backend:
    def __init__(self) -> None:
        self.names: list[str] = []

    def import_module(self, name: str) -> None:
        self.names.append(name)


def run(il: Backend) -> None:
    il.import_module("math")


def local() -> list[str]:
    il = Backend()
    il.import_module("json")
    return il.names


b = Backend()
run(b)
print(b.names)
print(local())
mod = il.import_module("json")
print(mod.dumps([1]))
