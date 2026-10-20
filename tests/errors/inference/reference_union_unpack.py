# error: reference union methods do not support unpacked arguments
class A:
    def read(self, amount: int) -> str:
        return "a" * amount


class B:
    def read(self, amount: int) -> str:
        return "b" * amount


def check(value: A | B) -> str:
    return value.read(*(1,))


print(check(A()))
