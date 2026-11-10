# A closed-union local that may be unassigned keeps an "is assigned" flag slot under its own
# slot's number. The union payload proof (PYSTACHY_IRCHECK=1) must name each slot as lowering
# does, or the flag's bool type replaces the union's storage type.
def pick(flag: bool, n: int) -> str:
    if flag:
        v: int | str = n
    if flag:
        if isinstance(v, int):
            return str(v + 1)
        return v
    return ""


def pick_text(flag: bool, s: str) -> str:
    if flag:
        v: int | str = s
    if flag:
        if isinstance(v, str):
            return v + "!"
        return str(v)
    return ""


print(repr(pick(True, 4)), repr(pick(False, 4)), repr(pick_text(True, "a")), repr(pick_text(False, "b")))
