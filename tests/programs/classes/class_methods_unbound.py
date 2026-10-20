# A static method called through its class before the class statement runs raises CPython's NameError
def early() -> int:
    return K.m(2)


print("start")
print(early())


class K:
    @staticmethod
    def m(x: int) -> int:
        return x * 10
