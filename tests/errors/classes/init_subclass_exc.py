# error: init_subclass_exc.py:9: error: a base that defines __init_subclass__ is not supported (CPython calls Failed.__init_subclass__() when it creates class Retry)
# CPython calls a base's __init_subclass__ when it creates a class that derives from it; a class
# without subclasses compiles (tests/programs/imports/deftime_uncalled.py).
class Failed(Exception):
    def __init_subclass__(cls) -> None:
        print("registered")


class Retry(Failed):
    pass


print("done")
