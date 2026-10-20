# A program's own len() is called, not folded: len(args) == 2 is what it returns
calls: list[int] = []


def len(x) -> int:
    calls.append(1)
    return 2


def f(*args):
    return "two" if len(args) == 2 else "not two"


print(f(1), f(1, 2, 3), sum(calls))
