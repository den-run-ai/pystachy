# pystachy: python-int
# CPython's TypeError and ValueError text for operands and bases int rejects.
x: int = 2 ** 70
y: int = 7


def report(label: str, error: Exception) -> None:
    print(label, type(error).__name__, error)


try:
    print(x + "a")
except TypeError as e:
    report("add", e)
try:
    print(y - [1])
except TypeError as e:
    report("sub", e)
try:
    print(x // "a")
except TypeError as e:
    report("floordiv", e)
try:
    print(y % "a")
except TypeError as e:
    report("mod", e)
try:
    print(y & 1.5)
except TypeError as e:
    report("and", e)
try:
    print(x ^ "a")
except TypeError as e:
    report("xor", e)
try:
    print(x << "a")
except TypeError as e:
    report("lshift", e)
try:
    print(y >> 1.0)
except TypeError as e:
    report("rshift", e)
try:
    print(x ** "a")
except TypeError as e:
    report("pow", e)
try:
    print(x < "a")
except TypeError as e:
    report("lt", e)
try:
    print(y >= [1])
except TypeError as e:
    report("ge", e)
try:
    print(bin("a"))
except TypeError as e:
    report("bin", e)
try:
    print(list(range(1.5)))
except TypeError as e:
    report("range", e)
print(x == "a", y != None, x == [1])
