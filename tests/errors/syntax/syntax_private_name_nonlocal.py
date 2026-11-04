# error: no binding for nonlocal '_C__value' found
def outer(unused):
    __value = 1

    class C:
        def method(self):
            nonlocal __value
