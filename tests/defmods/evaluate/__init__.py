"""Modules for tests/deftime_eval.py: what Pystachy runs of the def and class statements it
leaves uncompiled, the names CPython binds in a package and in a class body, and a global that a
module importing this one assigns first."""
import math
import os
import sys
import typing

NAMES = ["bb", "a"]
TABLE = {"a": 1}


class Base:
    "a class bound before the circular import below, whose module reads it"


def note(s: str) -> int:
    print("note:", s)
    return 1


def apply(x, f=(note("default"), {1}, lambda v: v)):
    "CPython evaluates the default when the def runs: Pystachy what it can compile of it"
    return x


def tally(x, seen={note("in a set"): [1]}):
    return x


from . import peer


def limit(k: int = LIMIT) -> int:
    "peer has assigned LIMIT when this def runs"
    return k


LIMIT = 5
if len(sys.argv) > 0:
    V: Base | None = None


class Consts:
    "Pystachy leaves this class uncompiled (an unannotated method): its body runs no code of the program"
    first = __path__[0] != ""
    where = __module__
    root = math.sqrt(4.0)
    got = TABLE.get("a")
    n = typing.cast(int, 3)
    cwd = os.getcwd()
    both = [*NAMES]
    merged = {**TABLE}
    a, (b, c) = 1, (2, 3)
    d, *e = 1, 2, 3
    order = sorted(NAMES, key=len)
    x: int = 1
    seen = __annotations__
    imp = __import__

    def get(self, k):
        return k
