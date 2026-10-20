# error: has no attribute '__deprecated__'
# warnings.deprecated sets the attribute __deprecated__ of the function it decorates, which it
# wraps with functools.wraps(): a function's attributes are not supported
import warnings


@warnings.deprecated("use g() instead")
def f() -> int:
    return 1


print(f())
