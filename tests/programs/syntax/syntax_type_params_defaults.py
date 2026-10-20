# A type parameter's default takes its kind's grammar (CPython's type_param_default and
# type_param_starred_default): an expression for a TypeVar or a ParamSpec, a star expression
# (*tuple[...] too) for a TypeVarTuple. A * inside the expression is valid for all three kinds;
# a TypeVar's or ParamSpec's default that starts with one is not (tests/errors/
# syntax_type_params_starred_*.py).
type Plain[T = int] = list[T]
type Hooks[**P = [int, str]] = int
type Spread[*Ts = *tuple[int, str]] = tuple[*Ts]
type Nested[T = tuple[*tuple[int, str]]] = tuple[T]
type Wide[
    T = list[*tuple[int]],
    **P = [int, *tuple[str, ...]],
    *Ts = *tuple[
        int,
        *tuple[str, ...],
    ],
] = tuple[T, *Ts]


class Box[T = int]:
    def __init__(self, value: T) -> None:
        self.value = value

    def same[U = str](self, x: U) -> U:
        return x


class Row[
    *Ts = *tuple[int, str],
]:
    def __init__(self, *items: *Ts) -> None:
        self.size = len(items)


def first[T = int](items: list[T]) -> T:
    return items[0]


def hooked[**P = [int, str]](n: int) -> int:
    return n + 1


def count[*Ts = *tuple[int, str]](*args: *Ts) -> int:
    return len(args)


def spread[
    T = tuple[*tuple[int, str]],
    **P = ...,
    *Ts = *tuple[int, ...],
](x: T, *rest: *Ts) -> int:
    return len(rest)


async def later[T = int](x: T) -> T:
    return x


async def later_count[*Ts = *tuple[int, str]](*args: *Ts) -> int:
    return len(args)


def never(x):
    # (never called, so only parsed: a class in a function, a class's ParamSpec and an async
    # function that is not a template do not compile)
    class Hook[**P = [int, *tuple[str, ...]]]:
        pass

    async def hook[**P = [int, str]]() -> None:
        pass

    type Local[T = int, **P = [int, str], *Ts = *tuple[int, str]] = tuple[T, *Ts]
    return x


print(Box(3).value, Box("s").value, Box(1).same("u"))
print(Row(1, "a").size, Row().size)
print(first([4, 5]), first(["a"]))
print(hooked(1), count(1, "x"), count())
print(spread((1, "a"), 2, 3), spread((2, "b")))
