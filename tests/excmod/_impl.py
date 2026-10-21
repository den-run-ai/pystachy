class Boom(ValueError):
    pass


class Worse(Boom):
    pass


def boom(n: int) -> None:
    if n == 0:
        raise Boom("bad")
    raise Worse("worse")
