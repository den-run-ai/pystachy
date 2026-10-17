# to_int and to_float convert as CPython's PyLong_AsLongLong and PyFloat_AsDouble do
from pyobj import import_module, of_int, of_str, of_float

b = import_module("builtins")
big = b.attr("pow").call([of_int(2), of_int(70)])
for o in [of_int(7), of_float(2.5), of_str("3.5"), big, b.attr("True")]:
    try:
        print("to_int", o.to_int())
    except (TypeError, OverflowError) as e:
        print("to_int", type(e).__name__, e)
    try:
        print("to_float", o.to_float())
    except (TypeError, OverflowError) as e:
        print("to_float", type(e).__name__, e)
