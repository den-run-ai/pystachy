# Minimal reproducer (main c179665): CPython prints 6; Pystachy rejects it with
#   error: closed union arithmetic requires narrowing with isinstance() first
def f(a: int, c: int) -> int | str:
    return (a if a > 0 else c) * 2


print(f(3, 4))
