# error: reference unions cannot mix native references with container members
# A tuple is a container member, which a union of objects does not hold (CPython prints True)
class C:
    pass


def pick(k: int) -> C | tuple[int, str]:
    if k == 0:
        return C()
    return (7, "seven")


print(isinstance(pick(1), tuple))
