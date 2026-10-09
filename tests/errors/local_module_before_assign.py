# error: local variable 'os' is read before its first assignment
# The function's local os hides the module os everywhere in it (CPython: UnboundLocalError).
import os


def g() -> str:
    a = os.name
    os = "x"
    return a + os


print(g())
