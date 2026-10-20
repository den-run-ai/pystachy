from typing import Any

# A separate first return establishes the type before compiling a recursive call.
def fact(n: int) -> Any:
    if n <= 1:
        return 1
    return n * fact(n - 1)

def unannotated(n):
    if n <= 1:
        return 1
    return n * unannotated(n - 1)

def annotated(n: int) -> int:
    return 1 if n <= 1 else n * annotated(n - 1)

print(fact(5), unannotated(5), annotated(5))

# A recursive procedure may discard or directly forward the None result.
def discard(n: int) -> Any:
    if n > 0:
        discard(n - 1)
    return None

def direct(n: int) -> Any:
    if n > 0:
        return direct(n - 1)

def first(n: int) -> Any:
    return second(n)

def second(n: int) -> Any:
    if n > 0:
        return first(n - 1)

print(discard(3), direct(3), first(3))

# Even an operator may legitimately accept the recursive None result.
class Sink:
    def __mul__(self, value) -> None:
        print(value)

def accepted(n: int) -> Any:
    if n > 0:
        return Sink() * accepted(n - 1)

print(accepted(2))
