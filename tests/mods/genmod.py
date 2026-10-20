"""Generators in an imported module (tests/programs/generators/gen_module.py): a class whose __iter__ yields, an
unannotated generator, and generators the program never calls, which compile only where called."""
from collections.abc import Iterator


class Lines:
    def __init__(self, text: str) -> None:
        self.text = text

    def __iter__(self) -> Iterator[str]:
        for line in self.text.splitlines():
            yield line

    def count(self) -> int:
        return len(self.text.splitlines())


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def echo():
    # never called: the value of a yield expression (send()) is not supported
    x = yield 1
    print(x)


def averager() -> Iterator[float]:
    # never called: it would need send()
    total = 0.0
    while True:
        total += yield total
