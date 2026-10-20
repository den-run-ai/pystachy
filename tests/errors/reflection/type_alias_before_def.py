# error: type_alias_before_def.py:2: error: name 'Row' is not defined (CPython evaluates this annotation when the def statement runs: quote it, or import annotations from __future__)
def f(r: Row) -> int:
    return len(r)


type Row = list[str]
print(f(["a"]))
