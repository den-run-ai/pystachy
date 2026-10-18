from pyobj import import_module, of_int, of_str, of_list

json = import_module("json")
s = json.attr("dumps").call([of_list([of_int(1), of_str("héllo")])])
print("json:", s)
d = json.attr("loads").call([of_str('{"a": [10, 20, 30]}')])
print(d[of_str("a")][of_int(1)].to_int() + 1)
try:
    json.attr("loads").call([of_str("{bad")])
except ValueError as e:
    print("caught:", e)
for o in [s, d, json]:
    o.close()
