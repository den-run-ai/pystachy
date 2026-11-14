class Number:
    def __call__(self) -> int:
        return 7


class Text:
    def __call__(self) -> str:
        return "ok"


class Result:
    # Conflicting annotations are a layout template: each specialization has one.
    def __init__(self, fn):
        if not callable(fn):
            raise TypeError("not callable")
        if isinstance(fn, Number):
            self.value: int = fn()
        else:
            self.value: str = fn()


class Separate:
    # Callable-controlled fields retain their specialization and assignment order.
    def __init__(self, fn):
        if not callable(fn):
            raise TypeError("not callable")
        if isinstance(fn, Number):
            self.number: int = fn()
        else:
            self.text: str = fn()


print(Result(Number()).value, Result(Text()).value)
a = Separate(Number())
b = Separate(Text())
print(a.number, b.text)
print(hasattr(a, "number"), hasattr(a, "text"))
print(hasattr(b, "number"), hasattr(b, "text"))
