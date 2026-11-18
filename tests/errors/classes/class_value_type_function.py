# error: type(x) of <function double> as a value is not supported
def double(x: int) -> int:
    return x * 2


t = type(double)
print(t)
