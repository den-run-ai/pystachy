# Deviation: a warning's message is a str or a Warning. One that is neither, which CPython keys
# and matches as the object itself, raises TypeError; and showwarning() or formatwarning() given
# a str makes a warning of its category of it, which a recorded message holds, where CPython keeps
# the str
import warnings

with warnings.catch_warnings(record=True) as log:
    warnings.showwarning("text", UserWarning, "f.py", 1)
    print(type(log[0].message).__name__, str(log[0].message))
try:
    warnings.warn(ValueError("not a warning"))
except TypeError as e:
    print("TypeError:", e)
try:
    warnings.warn(5)
except TypeError as e:
    print("TypeError:", e)
