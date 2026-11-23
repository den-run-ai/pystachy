from typing import Callable


def exercise() -> None:
    seen: list[int] = []

    def label(n):
        seen.append(n)
        if n == 1:
            return "one"

    def payload(n):
        if n == 1:
            return b"one"

    def concrete(text: str) -> str:
        return text.upper()

    def select(n):
        if n > 0:
            return n

    def consume(callback: Callable[[int], str]) -> str:
        return callback(1).upper()

    def recursive(n):
        if n == 1:
            return "done"
        if n > 1:
            value = recursive(n - 1)
            return value

    def annotated(n: int) -> str:
        if n:
            return "present"

    # Both call orders share the closure's captured list. A typed caller
    # still takes a str on a successful call with the same argument type.
    print(label(0) is None, concrete(label(1)), label(1) is not None)
    value: str | None = label(1)
    print(concrete(value), seen)
    print(None is payload(0), None is not payload(1))
    print(select(1) + 1, select(0) is None, select(1) is None)
    print(consume(label), label(0) is None, recursive(2) is not None)
    print(annotated(1) is not None)


exercise()
