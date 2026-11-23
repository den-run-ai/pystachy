# error: type alias 'Value': reference unions cannot mix native references with container members
# A recursive alias's type argument is a scalar or a tuple, not a class (CPython prints True)
class C:
    pass


type Value[F] = int | F | list[Value[F]]


def f(v: Value[C]) -> None:
    print(isinstance(v, int))


f(1)
