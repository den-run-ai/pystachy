# error: vtuple_key_float.py:4: error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not tuple[float, ...]
# a runtime-length tuple of floats is no key (as a fixed tuple of floats is none: #1460's scope)
def keys(xs: list[float]) -> None:
    d: dict[tuple[float, ...], int] = {tuple(xs): 1}
    print(d)


keys([1.5])
