# error: expected object, got <function f>: a function, bound method or lambda (a Callable value) as a value of object is not supported yet: call it, or store a <function f> where one is expected
# a function as a value of object
def f(n: int) -> int:
    return n


x: object = f
print(x)
