# A class deriving from ImportError or AttributeError, with no __init__ of its own, takes the keywords of its base's.
class I(ImportError):
    pass
class A(AttributeError):
    pass
i = I("x", name="m", path="p")
print(repr(i), str(i))
print(repr(A("y", obj=3)))
raise I("z", name="q")
