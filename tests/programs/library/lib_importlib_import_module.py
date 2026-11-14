# importlib.import_module() of a module that a string constant names, as a statement that binds
# a variable or stands alone: the import statement of that module, run where the call is.
# Through each way a module names the function, with a constant package for a relative name,
# and for a module that is not there.
import importlib
import importlib as il
from importlib import import_module
from importlib import import_module as load

print("start")
alpha = import_module("impmod_plug.alpha")
print(alpha.NAME, alpha.run(1))


def lazy(x: int) -> int:
    beta = importlib.import_module("impmod_plug.beta")
    return beta.run(x)


def relative() -> str:
    deep = il.import_module(".deep", "impmod_plug.sub")
    up = load("..alpha", package="impmod_plug.sub")
    return deep.where() + " " + str(deep.LEVEL) + " " + up.NAME


def optional() -> str:
    try:
        missing = import_module("impmod_no_such_module")
    except ModuleNotFoundError:
        return "missing"
    return "found"


def effects() -> None:
    import_module("impmod_plug.sub")
    importlib.import_module("impmod_plug.sub", None)


print(lazy(4))
print(relative())
print(optional())
effects()
text: object = import_module("json")
print(text.dumps([1, "a"]))
