# error: expected int, got str
def mixed(n):
    yield n
    yield "s"


print(list(mixed(1)))
