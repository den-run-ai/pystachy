from pyobj import import_module, of_str

m = import_module("side_fin")
m.attr("setup").call([of_str("x")])
print("pystachy done")
