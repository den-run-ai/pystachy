# error: unsupported call typing.final
from typing import final


def replacement(fn):
    return fn


@final
@replacement
def value() -> int:
    return 1


print(value())
