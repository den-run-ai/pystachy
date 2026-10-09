# error: pys_fmt_float() is declared with list[int], which RUNTIME has no entry to check: a function of runtime mode that the compiler does not call takes and returns int, float, str or None
def pys_fmt_float(x: list[int], spec: str) -> str: ...


def pys_str_upper(s: str) -> str:
    return pys_fmt_float([1], s)
