# error: any_mixed_return.py:10: error: parse() returns both int and str (each function has one return type)
# A return annotated Any is decided by what the function returns, as an unannotated one is: one type
# for each call's argument types, not a value of any type
from typing import Any


def parse(s: str) -> Any:
    if s.isdigit():
        return int(s)
    return s


print(parse("12"), parse("ab"))
