# Python code that prints, reached by every kind of operation: one stdout, in the order printed
from pyobj import import_module

print("1 before import")
m = import_module("side_noisy")
print("2 after import")
p = m.attr("P").call([])
print("3 before attr")
v = p.attr("value").to_int()
print("4 after attr", v)
s = str(p)
print("5 after str", s)
print("6 len", len(p))
import_module("sys").attr("stderr").attr("write").call([import_module("builtins").attr("str").call([m])])
print("7 end")
