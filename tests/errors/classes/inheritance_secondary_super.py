# error: super() in a primary hierarchy with a secondary base is not supported
class Root:
    def action(self) -> int:
        return 1


class First(Root):
    def action(self) -> int:
        return super().action()


class Second:
    def read(self) -> int:
        return 2


class Bad(First, Second):
    pass
