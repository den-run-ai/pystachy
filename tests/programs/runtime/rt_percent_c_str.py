# %c takes a str of exactly one character, as CPython checks it when it runs
import os


def one(s: str) -> str:
    return "[%c]" % s


print(one("é"), one("x"), "[%3c|%-3c]" % ("a", "€"), "%c%c" % (72, "i"))
for s in ["", "ab", "é", os.getenv("PYSTACHY_NOPE_Q_Z") or "xy"]:
    print(ascii(s))
print(one("ab"))
