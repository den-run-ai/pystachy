# str.split(sep, maxsplit): every negative maxsplit means no limit, -2**63 included
import sys

lo = -sys.maxsize - 1
print("a b c".split(" ", lo), "a b c".split(" ", -1), "a b c".split(" ", -2), "a b c".split(" ", 0))
print("a b c".split(" ", 1), "a b c".split(" ", sys.maxsize), "a,,b".split(",", lo), "".split(",", lo))
print("a b  c ".split(), " a b ".split(" ", lo), "xyxyx".split("y", lo + 1), "xyxyx".split("yx", 1))
