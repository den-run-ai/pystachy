# pystachy: dynamic-any
# Proven None-returning scalar consumers must not eagerly box expression results.


def assigned(n: int) -> None:
    for i in range(n):
        print(value := i + 1000)


def selected(n: int) -> None:
    for i in range(n):
        x = i + 1000
        y = i + 2000
        chosen = x if i % 2 else y
        print(chosen)


def unchanged(n: int) -> None:
    for i in range(n):
        x = i + 1000
        x = x if i % 2 else x
        print(x)


def inferred_assigned(n):
    for i in range(n):
        result = (value := i + 1000)
        print(result, value)


def inferred_selected(n):
    for i in range(n):
        x = i + 1000
        y = i + 2000
        chosen = x if i % 2 else y
        print(chosen)


inferred_assigned(0)
inferred_selected(0)
