def describe(x: int | str | None) -> str:
    if isinstance(x, (str, type(None))):
        if x is None:
            return 'none'
        return x.upper()
    return str(x + 1)

def refine(x: int | str | bool | float | None) -> str:
    if isinstance(x, (int, str)) and not isinstance(x, (str, bool)):
        return str(x + 1)
    if not isinstance(x, (int, str, type(None))):
        return str(x + 0.5)
    return 'other'

print(describe(None), describe('word'), describe(9))
print(refine(1), refine(1.5), refine(True), refine('word'), refine(None))
