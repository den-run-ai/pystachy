# Deliberately no opt-in: unannotated parameters specialize for the caller's types.
# Captured slots must use those types' widths, not this module's integer policy.
import intidentity


def capture_pair(first, second):
    def read() -> None:
        print("generic captured pair", first, second)

    return read


def capture_identity(value):
    def read() -> None:
        intidentity.keep(value)

    return read
