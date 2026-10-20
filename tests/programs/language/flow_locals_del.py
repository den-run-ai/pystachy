# A local deleted and given a value of another type: the value it holds is returned.
def f() -> int:
    value = "3"
    del value
    value = 3
    return value
print(f())
