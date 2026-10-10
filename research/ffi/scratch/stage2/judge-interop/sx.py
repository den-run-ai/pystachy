from pyobj import import_module, of_int

sys = import_module("sys")
try:
    sys.attr("exit").call([of_int(3)])
except Exception as e:
    print("caught Exception:", e)
print("after")
