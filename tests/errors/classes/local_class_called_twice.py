# error: local_class_called_twice.py:4: error: a class inside a function is not supported: make() is no function that runs at most once
# CPython makes a new class each time make() runs: it prints False
def make(n: int):
    class Box:
        def __init__(self, v: int) -> None:
            self.v = v

    return Box(n)


a = make(1)
b = make(2)
print(type(a) is type(b))
