# A return annotated Any is decided by what the function returns, as an unannotated one is:
# an int or a str, so int | str.
from typing import Any


def parse(s: str) -> Any:
    if s.isdigit():
        return int(s)
    return s


print(repr(parse("12")), repr(parse("ab")))
