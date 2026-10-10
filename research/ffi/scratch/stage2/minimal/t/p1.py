from pyobj import import_module, of_int, of_float, of_str, of_list

json = import_module("json")
math = import_module("math")
print("sqrt:", math.attr("sqrt").call([of_float(2.0)]).to_float())
s = json.attr("dumps").call([of_list([of_int(1), of_str("héllo"), of_float(2.5)])])
print("json:", s)
d = json.attr("loads").call([of_str('{"a": [10, 20, 30]}')])
print("a[1] =", d[of_str("a")][of_int(1)].to_int(), "len", len(d[of_str("a")]))
try:
    json.attr("loads").call([of_str("{bad")])
except ValueError as e:
    print("caught ValueError:", e)
try:
    math.attr("nope")
except AttributeError as e:
    print("caught AttributeError:", e)
import_module("builtins").attr("print").call([of_str("printed by Python")])
print("back in Pystachy")
