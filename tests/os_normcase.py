# os.path.normcase(): posixpath's, which gives a str path back as it is (the object itself), and
# raises CPython's TypeError for None
import os

p = "Src/Main.PY"
print(os.path.normcase(p), os.path.normcase(p) is p, repr(os.path.normcase("")))
o = os.getenv("PYSTACHY_NO_SUCH_VAR")
print(os.path.normcase(o if o is not None else "x"))
print(os.path.normcase(o))
