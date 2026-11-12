# error: reading exception args through a builtin exception type is not supported when user exceptions override args; catch the concrete user exception class
# pystachy: dynamic-any
class Error(Exception):
    @property
    def args(self) -> tuple[int, int]:
        return (7, 8)


try:
    raise Error(1)
except Exception as error:
    print(error.args)
