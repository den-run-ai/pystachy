# The decoding work of lib/re: re._decoded counts the code points it has decoded (CPython's re has
# no such counter). A str whose every byte is a code point (ASCII here) is read in place, with none
# decoded. Another is decoded once by an operation, which keeps it, also where a function that sub()
# calls matches another string, so a substitution's work grows with its string, not with the
# string's square. Callback spans are checked against CPython in lib_re_codepoints.py.
import re

outer = re.compile("a")
inner = re.compile("b")


def replacement(m) -> str:
    inner.match("bé")
    return "x"


for n in [10, 100, 1000, 10000]:
    for unit in ["a", "aé"]:
        before = re._decoded
        r = outer.sub(replacement, unit * n)
        work = re._decoded - before
        print(n, len(unit), r == ("x" + unit[1:]) * n, work, work <= len(unit) * n + 3)
