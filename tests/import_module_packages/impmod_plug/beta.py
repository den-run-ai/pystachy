import importlib
from importlib import import_module

NAME = "beta"


def run(x: int) -> int:
    return x * 10


def sibling() -> str:
    other = import_module(".alpha", __package__)
    return other.NAME


def nested() -> int:
    deep = importlib.import_module(".sub.deep", package=__package__)
    return deep.LEVEL
