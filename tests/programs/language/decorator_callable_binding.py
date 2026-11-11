from typing import Callable

events: list[str] = []


def default() -> int:
    events.append("default")
    return 5


def tagged(label: str):
    events.append("evaluate " + label)

    def decorate(f: Callable[[int], int]) -> Callable[[int], int]:
        events.append("apply " + label)

        def wrapper(n: int) -> int:
            events.append("call " + label + ":" + str(n))
            return f(n)

        return wrapper

    return decorate


@tagged("outer")
@tagged("inner")
def down(n: int = default()) -> int:
    return 0 if n == 0 else down(n - 1) + 1


print("ordered", down(2), events)
events.clear()


@tagged("even")
def even(n: int) -> int:
    return 1 if n == 0 else odd(n - 1)


@tagged("odd")
def odd(n: int) -> int:
    return 0 if n == 0 else even(n - 1)


print("mutual", even(3), odd(3), events)


def probe(f: Callable[[int], int]) -> Callable[[int], int]:
    try:
        f(1)
    except NameError as error:
        print("before binding", str(error))
    return f


@probe
def recursive(n: int) -> int:
    return 3 if n == 0 else recursive(n - 1)


print("after binding", recursive(2))
