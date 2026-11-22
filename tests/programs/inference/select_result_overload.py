# @overload stubs with Literal parameters change nothing: the body's returns, for each call's
# literal argument, decide what each call returns.
from typing import Literal, overload


@overload
def repair(s: str, logging: Literal[False] = False) -> str: ...
@overload
def repair(s: str, logging: Literal[True]) -> tuple[str, list[str]]: ...
def repair(s: str, logging: bool = False):
    fixed = s.strip()
    if logging:
        return fixed, ["stripped"]
    return fixed


print(repair(" a "))
value, log = repair(" b ", logging=True)
print(value, log)
