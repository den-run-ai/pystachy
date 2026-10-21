# A function's global alias is bound by its assignment, not by its target's definition.
from typing import Callable


def increment(value: int) -> int:
    return value + 1


def argument() -> int:
    print("argument")
    return 6


def call() -> int:
    return alias(argument())


def capture() -> Callable[[int], int]:
    return alias


for which in range(2):
    try:
        if which == 0:
            print(call())
        else:
            print(capture()(2))
    except NameError as e:
        print("NameError", e)
alias = increment
print(call(), capture()(2))


def chain() -> int:
    return final(10)


try:
    print(chain())
except NameError as e:
    print("NameError", e)
final = alias
print(chain())
