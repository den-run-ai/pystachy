# error: pys_format_str() is defined with list[str], which RUNTIME has no entry to check: a function of runtime mode that the compiler does not call takes and returns int, float, str or None
def pys_format_str(s: list[str], spec: str) -> str:
    return s[0] + spec
