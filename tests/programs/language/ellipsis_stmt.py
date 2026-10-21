# ... as a statement does nothing, as pass: in a function body, a branch, a loop or an except clause.
def f() -> None:
    ...


def g(x: int) -> int:
    if x > 0:
        ...
    return x


class P:
    def m(self) -> None:
        ...


try:
    int("x")
except ValueError:
    ...
f()
P().m()
for i in range(2):
    ...
print(g(3), "end")
