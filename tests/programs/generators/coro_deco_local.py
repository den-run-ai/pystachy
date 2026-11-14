# A function's own variable named coroutine hides types.coroutine, which the module imports: it
# is a decorator CPython calls, not @types.coroutine's mark
from types import coroutine


def outer():
    def coroutine(f):
        print("decorating")
        return f

    @coroutine
    def gen():
        yield 1

    return list(gen())


print(outer())
