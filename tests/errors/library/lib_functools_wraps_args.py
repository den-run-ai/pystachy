# error: lib_functools_wraps_args.py:9: error: update_wrapper() takes from 2 to 4 positional arguments but 5 were given
# CPython's TypeError, which counts the wrapper too
from functools import update_wrapper


def d(f):
    def w():
        pass
    return update_wrapper(w, f, (), (), 1)


d(len)
