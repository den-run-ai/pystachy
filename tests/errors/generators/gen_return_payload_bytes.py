# error: generator return payload cannot be retained: a bytes value cannot become an Any value
# pystachy: dynamic-any
def values():
    yield 1
    return b"bytes"


g = values()
print(next(g))
try:
    next(g)
except StopIteration as error:
    print(error.value)
