# A Callable as a member of a closed union: "a value or a function that makes one".
from typing import Callable, Optional, Union


def longer(s: str, n: int) -> bool:
    return len(s) > n


class Limit:
    def __init__(self, n: int) -> None:
        self.n = n

    def under(self, s: str, n: int) -> bool:
        return len(s) + n < self.n


def decide(f: bool | Callable[[str, int], bool], s: str) -> bool:
    if isinstance(f, bool):
        return f
    elif callable(f):
        return f(s, 1)
    else:
        raise AssertionError(f"invalid filter: {type(f)}")


def decide2(f: Union[bool, Callable[[str, int], bool]], s: str) -> bool:
    if callable(f):
        return f(s, 2)
    return not f


def decide3(f: Optional[Union[Callable[[str, int], bool], bool]], s: str) -> str:
    if f is None:
        return "none"
    if not callable(f):
        return "flag " + str(f)
    return "call " + str(f(s, 0))


def text(v: str | int | Callable[[], str]) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, int):
        return str(v + 1)
    return v()


def truth(v: int | Callable[[], int]) -> str:
    return "yes" if v else "no"


def pick(n: int) -> bool | Callable[[str, int], bool]:
    if n == 0:
        return False
    if n == 1:
        return longer
    if n == 2:
        return lambda s, k: s.startswith("a") and k > 0
    return Limit(n).under


print(decide(True, "a"), decide(False, "a"), decide(longer, "ab"), decide(longer, "a"))
print(decide(lambda s, n: s == "x", "x"), decide(Limit(4).under, "ab"), decide(Limit(4).under, "abc"))
print(decide2(True, "a"), decide2(False, "a"), decide2(longer, "abc"), decide2(longer, "ab"))
print(decide3(None, "a"), decide3(True, "a"), decide3(longer, "a"), decide3(longer, ""))
print(text("s"), text(41), text(lambda: "made"))
print(truth(0), truth(3), truth(lambda: 0))
print([decide(pick(i), "abc") for i in range(5)])

held: list[bool | Callable[[str, int], bool]] = [True, longer, False]
held.append(lambda s, n: n == 1)
print([decide(h, "") for h in held], [callable(h) for h in held])
named: dict[str, int | Callable[[], int]] = {"a": 1, "b": lambda: 2}


def add(values: dict[str, int | Callable[[], int]]) -> int:
    total = 0
    for key in sorted(values):
        item = values[key]
        total += item() if callable(item) else item
    return total


print(add(named))



def rebind() -> None:
    later: bool | Callable[[str, int], bool] = False
    print(callable(later), decide(later, "q"))
    later = longer
    print(callable(later), decide(later, "qq"))
    if callable(later):
        print(later("abc", 2), later("ab", 2))


rebind()
