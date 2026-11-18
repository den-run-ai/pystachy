# error: limit is int in class A and str in class C
# A class attribute read through any class's class object has one type.
class A:
    limit = 3


class C:
    limit = "four"


def lim(k: type) -> int:
    return k.limit


print(lim(A))
