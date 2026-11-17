# Documented deviation (#1512): module code binds a builtin's name only in an except clause that
# does not run, so the global len stays unbound, and reading it raises NameError. CPython finds the
# builtin where the module's global is unbound and prints "3 1".
def mylen(s: str) -> int:
    return -1


def f() -> int:
    return 1


try:
    n = f()
except ValueError:
    len = mylen
print(len("abc"), n)
