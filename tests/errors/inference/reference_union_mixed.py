# error: reference unions cannot mix native references with scalar or container members
class Stream:
    pass


def make(n: int) -> Stream | int:
    if n > 0:
        return n
    return Stream()


print(make(1))
