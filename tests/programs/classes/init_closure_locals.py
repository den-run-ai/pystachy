# Defs and lambdas in __init__ read its locals when they run, as in any function: those assigned
# on every path before the def or lambda compile (one that may be unassigned there is rejected,
# tests/errors/classes/init_closure_maybe_unassigned.py). A local may share a module global's name.


class Acc:
    def __init__(self, items: list[int], scale: int, text: str) -> None:
        total = 0
        for v in items:
            total += v
        if scale > 1:
            label = "scaled"
        else:
            label = "plain"
        try:
            extra = int(text)
        except ValueError:
            extra = -1

        def report() -> str:
            return f"{label}: {total * scale} {extra}"

        def outer() -> int:
            def inner() -> int:
                return total + len(items)

            return inner() + extra

        twice = lambda: total * 2
        self.text: str = report()
        self.n: int = outer() + twice()
        total = 100
        self.later: int = twice()


class Shadow:
    def __init__(self) -> None:
        y = [1, 2]

        def f() -> bool:
            return isinstance(y, list) and len(y) == 2

        self.ok: bool = f() and (lambda: y[0])() == 1


a = Acc([1, 2, 3], 2, "7")
print(a.text, a.n, a.later)
b = Acc([], 1, "x")
print(b.text, b.n, b.later)
print(Shadow().ok)
y = 5
print(y, Shadow().ok)
