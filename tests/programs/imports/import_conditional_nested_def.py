# A nested def's defaults and decorators (their names and arguments) run where the def statement
# runs: there, a read of a name that the function's import or from-import binds, where it may not
# have run, raises CPython's UnboundLocalError (also where the module's own import binds the name)
import re


def default(flag: bool) -> str:
    if flag:
        import posixpath

    def g(p: str, base=posixpath.basename) -> str:
        return base(p)
    return g("/a/b")


def shadowed(flag: bool) -> str:
    if flag:
        import re

    def inner(s: str, esc=re.escape) -> str:
        return esc(s)
    return inner("a.b")


def deco_call(flag: bool) -> int:
    if flag:
        import functools

    @functools.lru_cache(maxsize=None)
    def g(x: int) -> int:
        return x * 2
    return g(21)


def deco_dotted(flag: bool) -> int:
    if flag:
        import functools

    @functools.cache
    def g(x: int) -> int:
        return x + 1
    return g(1)


def surely(p: str) -> str:
    import posixpath

    def g(s: str, base=posixpath.dirname) -> str:
        return base(s)
    return g(p)


def from_deco(flag: bool) -> int:
    if flag:
        from functools import cache

    @cache
    def g(x: int) -> int:
        return x + 3
    return g(1)


def from_default(flag: bool) -> str:
    if flag:
        from posixpath import basename

    def g(p: str, base=basename) -> str:
        return base(p)
    return g("/x/y")


def deco_arg(flag: bool) -> int:
    if flag:
        import posixpath
    import functools

    @functools.lru_cache(maxsize=len(posixpath.sep))
    def g(x: int) -> int:
        return x * 3
    return g(2)


for flag in [True, False]:
    try:
        print(default(flag))
    except UnboundLocalError as e:
        print("default:", e)
    try:
        print(shadowed(flag))
    except UnboundLocalError as e:
        print("shadowed:", e)
    try:
        print(deco_call(flag))
    except UnboundLocalError as e:
        print("deco_call:", e)
    try:
        print(deco_dotted(flag))
    except UnboundLocalError as e:
        print("deco_dotted:", e)
    try:
        print(from_deco(flag))
    except UnboundLocalError as e:
        print("from_deco:", e)
    try:
        print(from_default(flag))
    except UnboundLocalError as e:
        print("from_default:", e)
    try:
        print(deco_arg(flag))
    except UnboundLocalError as e:
        print("deco_arg:", e)
print(surely("/a/b"), re.escape("x.y"))
