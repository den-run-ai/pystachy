# error: class attribute 'x' of 'C' used in a class-body default is not supported
# (a name the body binds twice is no constant)
class C:
    x = 1
    y: int = x
    x = 2


print(C.y)
