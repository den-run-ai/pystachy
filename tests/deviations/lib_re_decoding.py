# The decoding work of lib/re: re._decoded counts the code points it has decoded (CPython's re has
# no such counter). An operation decodes its subject once and keeps it, also where a function that
# sub() calls matches another string, so a substitution's work grows with its string, not with
# the string's square. Callback spans are checked against CPython in lib_re_codepoints.py.
import re

outer = re.compile("a")
inner = re.compile("b")


def replacement(m) -> str:
    inner.match("b")
    return "x"


for n in [10, 100, 1000, 10000]:
    before = re._decoded
    r = outer.sub(replacement, "a" * n)
    work = re._decoded - before
    print(n, r == "x" * n, work, work <= n + 1)
