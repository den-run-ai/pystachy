# error: reference unions cannot mix native references with scalar or container members
class Stream:
    pass


def check(value: Stream | int) -> None:
    pass


check(Stream())
