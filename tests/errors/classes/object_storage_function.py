# error: a function or Callable value as a value of object is not supported yet
# a function as a value of object
def f(n: int) -> int:
    return n


x: object = f
print(x)
