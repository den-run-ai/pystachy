# A static or class method called through an object that is None raises CPython's AttributeError
# before its arguments are evaluated
class K:
    @staticmethod
    def m(x: int) -> int:
        return x * 10

    @classmethod
    def c(cls, x: int) -> int:
        return x


def say(v: int) -> int:
    print("evaluated", v)
    return v


def get(n: int) -> K | None:
    print("get", n)
    return K() if n else None


print(get(1).m(say(3)), get(1).c(say(4)))
print(get(0).c(say(5)))
