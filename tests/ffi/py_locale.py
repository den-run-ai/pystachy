# Python's setlocale (de_DE.UTF-8, built by tests/ffi/run.sh when it can) does not change how
# Pystachy writes and reads floats: CPython's float text does not depend on the locale either
from pyobj import import_module, of_str

loc = import_module("locale")
try:
    loc.attr("setlocale").call([loc.attr("LC_ALL"), of_str("de_DE.UTF-8")])
except Exception as e:
    print("no de_DE.UTF-8 locale here")
x = 1.5
print(x, x / 3, round(2.675, 2), f"{x:.3f}", float("2.5") * 2, 1e300 * 10, repr(0.1))
