# a library module as packages write them: one function imports a backend that its argument
# names, which Pystachy cannot compile, and which this module's importer never calls
from importlib import import_module

VALUE = 7


def load_backend(name: str):
    return import_module("impmod_plug." + name)


def static_backend() -> str:
    alpha = import_module("impmod_plug.alpha")
    return alpha.NAME
