# error: reflected operator methods are not supported (complex + Right calls Right.__radd__)
class Right:
    def __radd__(self, other: complex) -> str:
        return "Right.__radd__"


print(1j + Right())
