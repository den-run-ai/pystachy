# type(x).__doc__ of an x that is None is NoneType's own, where the class binds __doc__; another
# class attribute read through NoneType's class object raises AttributeError.
class A:
    __doc__ = "A documentation"
    limit = 3


def doc(o: A | None) -> None:
    try:
        print(type(o).__doc__)
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print(type(o).limit)
    except AttributeError as e:
        print("AttributeError:", e)


doc(A())
doc(None)
