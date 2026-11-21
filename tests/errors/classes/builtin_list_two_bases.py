# error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base
class Mixin:
    def hello(self) -> str:
        return "hello"


class Stack(list[int], Mixin):
    pass
