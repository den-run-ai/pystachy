# error: class attribute 'm' of 'C' holds a function (m = ...): reading it through an object is not supported (CPython binds the object to the function's first parameter, as for a method); read it through the class (C.m), or define m with def
def first(a, b=0):
    return b


class C:
    m = first

    def call(self) -> int:
        f = self.m
        return f(5)


print(C().call())
