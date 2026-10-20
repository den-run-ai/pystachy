# error: lib_functools_wraps_value.py:8: error: functools.wraps() is supported as the decorator of a def, @wraps(wrapped): call update_wrapper(wrapper, wrapped) to name another function
from functools import wraps


def d(f):
    def w(x):
        return f(x)
    deco = wraps(f)
    return deco(w)


print(d(abs)(-1))
