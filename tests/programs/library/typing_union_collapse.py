# typing.Union drops repeated members, as typing does: Union[int, int, None] and
# Union[int, None, None] are Optional[int], and Union[int] is int
from typing import Optional, Union


def f(x: Union[int, int, None]) -> int:
    return 0 if x is None else x


def g(x: Union[str, None, None]) -> str:
    return "-" if x is None else x


def h(x: Union[int]) -> Union[float, float]:
    return x / 2


def k(x: Optional[int] | None) -> int | None | None:
    return x


print(f(None), f(1), g(None), g("s"), h(3), k(None), k(4))
