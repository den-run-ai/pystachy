# error: type_alias_expansion.py:20: error: the type aliases this annotation names expand to more than 65536 nodes (not supported: simplify them)
# (each alias names the one before twice: CPython stores int | int, Pystachy expands them all)
A0 = int
A1 = A0 | A0
A2 = A1 | A1
A3 = A2 | A2
A4 = A3 | A3
A5 = A4 | A4
A6 = A5 | A5
A7 = A6 | A6
A8 = A7 | A7
A9 = A8 | A8
A10 = A9 | A9
A11 = A10 | A10
A12 = A11 | A11
A13 = A12 | A12
A14 = A13 | A13
A15 = A14 | A14
A16 = A15 | A15
def f(x: A16) -> int:
    return x + 1
print(f(1))
