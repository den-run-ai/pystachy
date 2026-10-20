"""Mutation, exception edges and GC lifetime checks from independent review."""

def desc(x: int | float | bool | str | None) -> str:
    if isinstance(x, bool):
        return 'B' + str(x)
    if isinstance(x, int):
        return 'I' + str(x)
    if isinstance(x, float):
        return 'F' + str(x)
    if isinstance(x, str):
        return 'S' + x
    return 'N'

def bool_int(x: bool | int | str | None) -> str:
    if isinstance(x, int):
        if isinstance(x, bool):
            return 'bool' if x else 'false'
        return 'int:' + str(x + 1)
    if x is None:
        return 'none'
    return x.upper()

def exception(x: int | str | None, flag: int) -> str:
    try:
        if flag == 0:
            raise ValueError('before')
        x = 'changed'
        if flag == 1:
            raise ValueError('after')
        x = 22
    except ValueError:
        return desc(x)
    return desc(x)

def finalized(flag: bool) -> str:
    x: int | str | None = 1
    try:
        if flag:
            x = 'changed'
            raise ValueError('oops')
        x = None
    except ValueError:
        pass
    finally:
        print(desc(x))
    return desc(x)

def capture() -> str:
    x: int | str = 42
    def read() -> str:
        if isinstance(x, int):
            return 'int:' + str(x)
        return x.upper()
    a = read()
    x = 'word'
    return a + ',' + read()

def nonlocal_snapshot() -> str:
    x: int | str = 42
    def change() -> None:
        nonlocal x
        x = 'changed'
    local = x
    if isinstance(local, int):
        change()
        return str(local) + ':' + desc(x)
    return 'bad'

def opt_float(x: float | None) -> str:
    u: float | str | None = x
    return desc(u)

def opt_bool(x: bool | None) -> str:
    u: bool | str | None = x
    return desc(u)

def churn(x: int | str | None) -> str:
    size = 0
    for i in range(100):
        dummy = str(i) * 50
        size += len(dummy)
    return desc(x) + ":" + str(size)

print(bool_int(True), bool_int(False), bool_int(10), bool_int('word'), bool_int(None))
print(exception(5, 0), exception('original', 0), exception(None, 0), exception(5, 1), exception(5, 2))
print(finalized(True), finalized(False))
print(capture(), nonlocal_snapshot())
print(opt_float(None), opt_float(1.5), opt_bool(None), opt_bool(False), opt_bool(True))
print(churn('dynamically allocated' * 3), churn(42), churn(None))
