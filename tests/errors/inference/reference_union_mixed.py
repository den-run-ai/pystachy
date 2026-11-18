# error: reference unions cannot mix native references with container members
class Stream:
    pass


def check(value: Stream | list[int]) -> None:
    pass


check(Stream())
