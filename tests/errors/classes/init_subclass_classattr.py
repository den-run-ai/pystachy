# error: init_subclass_classattr.py:8: error: a base that defines __init_subclass__ is not supported (CPython calls Failed.__init_subclass__() when it creates class Retry)
# A class attribute __init_subclass__ is what CPython calls (here 0: TypeError: 'int' object is not
# callable) when it creates a class that derives from it.
class Failed(Exception):
    __init_subclass__ = 0


class Retry(Failed):
    pass


print("done")
