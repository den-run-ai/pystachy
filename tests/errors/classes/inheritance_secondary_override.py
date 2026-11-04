# error: secondary base method 'read' needs a matching instance method signature
class First:
    pass


class Second:
    def read(self, key: int) -> int:
        return key


class Impl(First, Second):
    pass


class Bad(Impl):
    def read(self, key: str) -> int:
        return len(key)
