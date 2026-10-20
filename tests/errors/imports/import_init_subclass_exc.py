# error: emods/init_subclass_exc.py:6: error: a base that defines __init_subclass__ is not supported (CPython calls Failed.__init_subclass__() when it creates class Retry)
# CPython calls a base's __init_subclass__ when the class statement runs, which in an imported
# module is when the module is imported, whether or not the program uses the class.
import emods.init_subclass_exc
print("imported")
