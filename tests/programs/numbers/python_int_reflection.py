# pystachy: python-int
# type() reflection of a promoting value names CPython's int, as a native int's does.
x: int = 2 ** 70
y: int = 5
n = len("abc")
print(type(x).__name__, type(y).__qualname__, type(x).__module__)
print(x.__class__.__name__, y.__class__.__name__, type(n).__name__)
print(type(x) == type(y), type(x) is type(n), type(y) != type(n))
print(type(x) == type("s"), type(x) is not type(None))
