# error: class attribute 'x' of 'A' used in a class-body default is not supported
x = 10


class A:
    x: int = 1
    y: int = x + 1


print(A().y)
