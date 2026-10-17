from pyobj import import_module, of_int
print("before")
import_module("sys").attr("exit").call([import_module("builtins").attr("bool").call([of_int(1)])])
print("not reached")
