# Definite assignment (flow.py) of names that := binds in an if statement's test: where the test
# is true, every operand of its and ran, so the branch reads them without a check. Each negative
# control reads a name that the true test (or the false branch, or the code after the statement)
# may not have bound: it must still raise UnboundLocalError, as CPython does, never read a slot
# that was not assigned (0 or a null pointer).


def guarded(a: int, b: int) -> int:
    if a > 0 and (c := b) > 0:
        return c
    return -1


def either(a: bool, b: int) -> int:
    if a or (c := b) > 0:
        try:
            return c
        except UnboundLocalError:
            return -2
    return -1


def nested_or(a: bool, b: bool) -> int:
    if (a and (c := 1) > 0) or b:
        try:
            return c
        except UnboundLocalError:
            return -3
    return -1


def first_of_or(a: int) -> int:
    if ((c := a) > 5 or (d := a) > 1) and c > 0:
        return c
    return -1


def operand(a: bool, b: int) -> int:
    # (an operand of and runs only where the one before it was true, which need not bind c)
    if (a or (c := b) > 0) and c > 0:
        return c
    return -1


def else_branch(a: int) -> int:
    if a > 0 and (c := a) > 3:
        return c
    else:
        try:
            return c
        except UnboundLocalError:
            return -4


def after(a: int) -> int:
    if a > 0 and (c := a) > 3:
        pass
    try:
        return c
    except UnboundLocalError:
        return -5


def text(a: str, b: str) -> str:
    if a and (s := b + "!") and len(s) > 1:
        return s
    if a or (t := b):
        try:
            return t
        except UnboundLocalError:
            return "unbound"
    return "none"


def alternatives(t: tuple[int, int]) -> int:
    match t:
        case (0, v) | (v, 0):
            pass
    try:
        return v
    except UnboundLocalError:
        return -6


def guarded_alternatives(t: tuple[str, str]) -> str:
    match t:
        case ("", w) | (w, "") if w:
            return w
        case (x, y):
            return x + y
    return "miss"


print(guarded(1, 2), guarded(1, -2), guarded(-1, 2))
print(either(True, 5), either(False, 5), either(False, -5))
print(nested_or(True, False), nested_or(False, True), nested_or(False, False))
print(first_of_or(9), first_of_or(3), first_of_or(0))
for a, b in [(True, 5), (False, 5), (False, -5)]:
    try:
        print(operand(a, b))
    except UnboundLocalError:
        print("operand unbound")
print(else_branch(5), else_branch(2), else_branch(-1))
print(after(5), after(2), after(-1))
print(text("x", "y"), text("", "y"), text("x", ""), text("", ""))
print(alternatives((0, 3)), alternatives((4, 0)), alternatives((1, 1)))
print(guarded_alternatives(("", "a")), guarded_alternatives(("b", "")), guarded_alternatives(("", "")), guarded_alternatives(("c", "d")))
