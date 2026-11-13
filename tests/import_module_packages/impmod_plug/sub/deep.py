from importlib import import_module

LEVEL = 2


def where() -> str:
    return __name__


def up() -> str:
    parent = import_module("..alpha", __package__)
    return parent.NAME
