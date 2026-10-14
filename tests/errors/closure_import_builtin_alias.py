# error: inner() reads 'down', which is not assigned yet where it is defined: not supported
# Builtin import aliases are not closure values; retain the existing explicit rejection.
def outer() -> int:
    from math import floor as down

    def inner() -> int:
        return down(2.7)

    return inner()


print(outer())
