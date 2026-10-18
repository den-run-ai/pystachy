# one stdin: Pystachy's input() and sys.stdin.readline(), and Python's sys.stdin, read it in turn
import sys
from pyobj import import_module

a = input()
py = import_module("sys").attr("stdin")
b = str(py.attr("readline").call([]))
c = sys.stdin.readline()
d = input("prompt> ")
rest = str(py.attr("read").call([]))
print()
print(repr(a), repr(b), repr(c), repr(d), repr(rest))
try:
    input()
except EOFError as e:
    print("EOFError", e)
