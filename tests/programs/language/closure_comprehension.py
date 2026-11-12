# A comprehension has one shared cell per captured name, freshly made each time it runs.
from typing import Callable


def table(xs: list[int]) -> list[Callable[[], int]]:
    return [lambda: x for x in xs]


def clauses(rows: list[list[int]]) -> list[Callable[[], int]]:
    return [lambda: y for row in rows for y in row]


def read_all(fs: list[Callable[[], int]]) -> list[int]:
    return [f() for f in fs]


def from_reader(read) -> list[int]:
    return [read(), read() + 1]


print("late", read_all(table([1, 2, 3])))
first = table([4, 5])
second = table([6, 7])
print("separate", read_all(first), read_all(second), read_all(table([])))
print("clauses", read_all(clauses([[1, 2], [], [3, 4]])))
print("early", [(lambda x=x: x)() for x in [1, 2, 3]])
module_readers = [lambda: x for x in [8, 9]]
print("module", [f() for f in module_readers])


def scopes() -> None:
    x = 40
    read_outer = lambda: x
    inner = [lambda: x for x in range(read_outer(), read_outer() + 2)]
    print("shadow", [f() for f in inner], read_outer(), x)
    x = 50
    print("restored", [f() for f in inner], read_outer(), x)
    fresh = [lambda: x for x in from_reader(lambda: x)]
    print("iterable scope", [f() for f in fresh], read_outer())
    nested = [[lambda: x for x in range(start, start + 2)] for start in [10, 20]]
    print("nested", [[f() for f in row] for row in nested])
    both = [[lambda: (x, y) for y in [1, 2]] for x in [3, 4]]
    print("both", [[f() for f in row] for row in both])
    repeated = [lambda: x for x in [1, 2] for _ in range(2) for x in [x + 10]]
    print("repeated", [f() for f in repeated])
    functions = {x: lambda: x for x in [5, 6]}
    print("dict", functions[5](), functions[6]())
    immediate = [(lambda: x)() for x in [1, 2, 3]]
    print("immediate", immediate)
    makers = [lambda: (lambda: x) for x in [7, 8]]
    print("nested lambdas", [f()() for f in makers])
    escaped: list[Callable[[], int]] = []

    def keep(f: Callable[[], int]) -> bool:
        escaped.append(f)
        return True

    values = [x for x in [1, 2, 3] if x < 3 and keep(lambda: x)]
    print("filter", values, read_all(escaped))
    print("set", sorted({(lambda: x)() for x in [2, 1, 2]}))
    try:
        [lambda: x for x in [1, 2] if 1 // (2 - x)]
    except ZeroDivisionError:
        print("exception scope", read_outer(), x)


scopes()


def deleted_outer() -> None:
    x = 10
    callbacks = [lambda: x for x in [1, 2]]
    del x
    print("deleted outer", [f() for f in callbacks])


deleted_outer()
