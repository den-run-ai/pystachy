# Where a function's import may not have run, a lambda in it reads the name as CPython's closures
# do (NameError: cannot access free variable) and checks where it runs, also when the import comes
# after it; the function's comprehensions and generator functions read it as the function does
# (UnboundLocalError).
def with_lambda(flag: bool) -> str:
    if flag:
        import re
    f = lambda s: re.escape(s)
    return f("a.b")


def lambda_first(flag: bool) -> str:
    f = lambda s: re.escape(s)
    if flag:
        import re
    return f("c.d")


def lambda_default(flag: bool) -> str:
    if flag:
        import re
    f = lambda s, esc=re.escape: esc(s)
    return f("e.f")


def listcomp(flag: bool) -> str:
    if flag:
        import re
    return str([re.escape(s) for s in ["g.h", "i"]])


def setcomp(flag: bool) -> str:
    if flag:
        import re
    return str({re.escape(s) for s in ["j.k"]})


def dictcomp(flag: bool) -> str:
    if flag:
        import re
    return str({s: re.escape(s) for s in ["l.m"]})


def gen(flag: bool):
    if flag:
        import re
    yield re.escape("n.o")


def show(name: str, flag: bool) -> None:
    try:
        if name == "with_lambda":
            r = with_lambda(flag)
        elif name == "lambda_first":
            r = lambda_first(flag)
        elif name == "lambda_default":
            r = lambda_default(flag)
        elif name == "listcomp":
            r = listcomp(flag)
        elif name == "setcomp":
            r = setcomp(flag)
        elif name == "dictcomp":
            r = dictcomp(flag)
        else:
            r = str(list(gen(flag)))
        print(flag, name, r)
    except NameError as e:
        print(flag, name, type(e).__name__ + ":", e)


for flag in (True, False):
    for name in ("with_lambda", "lambda_first", "lambda_default", "listcomp", "setcomp", "dictcomp", "gen"):
        show(name, flag)
