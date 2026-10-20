# error: import_new_pkg.py:7: error: class emods.newpkg.Retry is not supported: the special method __new__ of its base emods.newpkg.Failed is not supported (CPython calls it to make each object of the class)
# A class of a package's own module (its __init__.py) that inherits __new__ from its base is an
# error where the program uses it, as one that defines it is.
import emods.newpkg

try:
    raise emods.newpkg.Retry("again")
except Exception as e:
    print(e)
