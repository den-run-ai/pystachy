# Returned callables and generators need no general type reflection support to be rejected.
from typing import Callable, Iterator


def answer() -> int:
    return 42


class FunctionResult:
    def __init__(self) -> Callable[[], int]:
        return answer


class GeneratorResult:
    def __init__(self) -> Iterator[int]:
        print("generator body must not run")
        yield 1


try:
    FunctionResult()
except TypeError as e:
    print("TypeError", e)
try:
    GeneratorResult()
except TypeError as e:
    print("TypeError", e)
