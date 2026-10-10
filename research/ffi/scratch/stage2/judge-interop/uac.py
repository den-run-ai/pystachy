from pyobj import import_module, of_str

json = import_module("json")
f = json.attr("dumps")
f.close()
try:
    print(f.call([of_str("x")]))
except AttributeError as e:
    print("AttributeError")
except TypeError as e:
    print("TypeError")
print("after")
