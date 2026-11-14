# error: cannot compare int == Equal
class Equal:
    def __eq__(self, other: object) -> bool:
        return True


def f(v: int | complex) -> bool:
    return v == Equal()


print(f(1j))
