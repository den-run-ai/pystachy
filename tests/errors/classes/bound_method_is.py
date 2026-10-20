# error: bound_method_is.py:10: error: 'is' between bound methods is not supported: CPython makes a new method object each time one is read (compare them with ==)
class A:
    def m(self) -> int:
        return 1


a = A()
f = a.m
g = a.m
print(f is g)
