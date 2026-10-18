# a float crosses as it is, in both directions: the sign of zero, infinities, NaN
from pyobj import import_module, of_float

m = import_module("math")
for x in [-0.0, 0.0, float("inf"), float("-inf"), float("nan"), -1.5e-310]:
    o = of_float(x)
    print(str(o), o.to_float(), m.attr("copysign").call([of_float(1.0), o]).to_float())
