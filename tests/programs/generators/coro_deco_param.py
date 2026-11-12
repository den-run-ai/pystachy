# A parameter named types hides the module types: @types.coroutine calls its coroutine()
import types


class Fake:
    def coroutine(self, f):
        print("fake decorating")
        return f


def outer(types):
    @types.coroutine
    def gen():
        yield 1

    return list(gen())


print(outer(Fake()))
