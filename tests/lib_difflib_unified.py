# lib/difflib.py: unified_diff() over lists of lines, with names, dates, context sizes and
# line terminators, and restore() of an ndiff-style delta, against CPython's difflib. Cases after
# CPython's Lib/test/test_difflib.py.
import difflib

a = ["one\n", "two\n", "three\n", "four\n", "five\n", "six\n", "seven\n", "eight\n"]
b = ["one\n", "tree\n", "three\n", "four\n", "five\n", "six\n", "seven\n", "eight\n", "nine\n"]

print("".join(difflib.unified_diff(a, b)), end="")
print("".join(difflib.unified_diff(a, b, "a.txt", "b.txt", "2026-10-19", "2026-10-20")), end="")
print("".join(difflib.unified_diff(a, b, n=0)), end="")
print("".join(difflib.unified_diff(a, b, n=1)), end="")
print(list(difflib.unified_diff(["x"], ["y"], lineterm="")))
print(list(difflib.unified_diff(a, a)))
none: list[str] = []
print(list(difflib.unified_diff(none, ["only\n"])))
print(list(difflib.unified_diff(["only\n"], none)))

delta = ["  one\n", "- two\n", "+ tree\n", "?  ^\n", "  three\n", "+ four\n"]
print("".join(difflib.restore(delta, 1)), end="")
print("".join(difflib.restore(delta, 2)), end="")
