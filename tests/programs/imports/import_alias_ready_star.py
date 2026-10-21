# Resolving a static alias must precede unpacking its arguments too.
def target(x: int) -> int:
    return x + 1


def args() -> tuple[int]:
    print("star arguments")
    return (4,)


def call() -> int:
    return alias(*args())


try:
    print(call())
except NameError as e:
    print("NameError", e)
alias = target
print(call())
