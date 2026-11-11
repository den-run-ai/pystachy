# dict of name -> bound-method/function hooks (mypy/plugins/default.py, mypyc specializers via decorators)
from typing import Callable
Hook = Callable[[str], str]
REG: dict[str, Hook] = {}
def register(name: str) -> Callable[[Hook], Hook]:
    def deco(f: Hook) -> Hook:
        REG[name] = f
        return f
    return deco
@register("upper")
def up(s: str) -> str:
    return s.upper()
@register("rev")
def rev(s: str) -> str:
    return s[::-1]
print([REG[k]("ab") for k in sorted(REG)])
