# error: the attributes of a class object (type[object]) other than its names and its class's attributes
class A:
    limit = 3


class C:
    limit = 4


def lim(k: type) -> int:
    return k.limit


print(lim(A))
