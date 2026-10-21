# Decorators for tests/programs/imports/import_try_decorator.py
from typing import Callable


def deco(f: Callable[[], int]) -> Callable[[], int]:
    print("deco runs")
    return f


def fac(n: int) -> Callable[[Callable[[], int]], Callable[[], int]]:
    print("fac runs", n)
    return deco
