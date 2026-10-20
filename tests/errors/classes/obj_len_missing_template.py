# error: object of type 'C' has no len() (compiling n(C)
class C:
    pass


def n(o):
    return len(o)


print(n(C()))
