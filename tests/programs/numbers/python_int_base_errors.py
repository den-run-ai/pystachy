# pystachy: python-int
# int(value, base) checks the base before the value, with CPython's errors.


def report(label: str, error: Exception) -> None:
    print(label, type(error).__name__, error)


try:
    print(int(5, 100))
except ValueError as e:
    report("int base range", e)
try:
    print(int("1", 2 ** 70))
except ValueError as e:
    report("int huge base", e)
try:
    print(int(5, 10))
except TypeError as e:
    report("int non-string", e)
try:
    print(int("12", "3"))
except TypeError as e:
    report("int base type", e)
print(int("ff", 16), int("-0b101", 0), int("z" * 13, 36))
