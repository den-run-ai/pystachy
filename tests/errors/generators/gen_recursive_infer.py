# error: cannot infer what walk() yields: it calls itself before its first yield; annotate its return type (-> Iterator[T])
def walk(n):
    if n > 0:
        yield from walk(n - 1)
    yield n


print(list(walk(3)))
