# error: the attributes of a class object (type[object]) other than its names and its class's attributes
# No class of the program binds the name: there is nothing a class object could give for it.
class A:
    limit = 3


class C:
    limit = 4


def lim(k: type) -> int:
    return k.missing


print(lim(A))
