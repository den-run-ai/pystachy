from ffi import export
from pyobj import import_module, of_str, of_int


@export
def roundtrip(s: str) -> str:
    json = import_module("json")
    v = json.attr("loads").call([of_str(s)])
    r = json.attr("dumps").call([v])
    out = str(r)
    for o in [r, v, json]:
        o.close()
    return out


@export
def total(module: str, func: str, n: int) -> int:
    # calls back into Python (any module's function) n times
    f = import_module(module).attr(func)
    t = 0
    for i in range(n):
        t += f.call([of_int(i)]).to_int()
    return t


@export
def strict(s: str) -> int:
    return import_module("json").attr("loads").call([of_str(s)]).to_int()


@export
def twice(n: int) -> int:
    parts = [str(n)] * 50  # garbage, so collections happen inside the nested entry
    return len(",".join(parts)) * 0 + 2 * n
