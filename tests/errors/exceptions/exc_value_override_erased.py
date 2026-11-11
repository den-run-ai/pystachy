# error: reading exception value through a builtin exception type is not supported when user exceptions override value; catch the concrete user exception class
# pystachy: dynamic-any
class Done(StopIteration):
    @property
    def value(self) -> int:
        return 42


try:
    raise Done(1)
except StopIteration as error:
    print(error.value)
