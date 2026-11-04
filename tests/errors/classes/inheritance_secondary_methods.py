# error: both bases declare method 'read'
class First:
    def read(self) -> int:
        return 1


class Second:
    def read(self) -> int:
        return 2


class Bad(First, Second):
    pass
