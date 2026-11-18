# The import of import_module in one function binds it there only: the module's own function
# import_module() and a nested function of that name are what other functions call.
def imported() -> str:
    from importlib import import_module

    mod = import_module("json")
    return mod.dumps([1])


def import_module(name: str) -> str:
    return "module " + name


def other() -> str:
    found = import_module("json")
    return found


def nested() -> str:
    def import_module(name: str) -> str:
        return "nested " + name

    found = import_module("json")
    return found


print(imported())
print(other())
print(nested())
