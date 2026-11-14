# error: reference unions cannot mix native references with scalar or container members
class Sentinel:
    pass


def f(v: int | complex | Sentinel) -> None:
    print(v)


f(1)
