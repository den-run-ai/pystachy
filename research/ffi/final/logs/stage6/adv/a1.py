from pyobj import import_module

m = import_module("side_bad")
print("start")
n = m.attr("noisy").call([]).to_int()
print(" | pys:", n)
m.attr("install").call([])
try:
    print("hidden")
    print("hidden2")
except ValueError as e:
    m.attr("restore").call([])
    print("caught", e)
print("end")
