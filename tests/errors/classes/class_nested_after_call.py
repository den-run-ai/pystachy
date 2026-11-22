# error: class_nested_after_call.py:13: error: class Outer.Inner is not supported after a call in the decorators, bases or body of class Outer: Pystachy makes a nested class before the class around it, and CPython runs those first
# A class nested in a class body is made before the class around it, so a call before it (here a
# class attribute's value) would run after the nested class's body, where CPython prints
# "log 1" first.
def log(x: int) -> int:
    print("log", x)
    return x


class Outer:
    a = log(1)

    class Inner:
        b = log(2)


print(Outer.a, Outer.Inner.b)
