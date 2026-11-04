# error: secondary base methods may not use super() or read or write the instance
class First:
    pass


class Second:
    def store(self, n: int) -> None:
        self.value = n


class Bad(First, Second):
    pass
