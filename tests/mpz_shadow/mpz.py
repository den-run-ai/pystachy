# A user module named mpz must retain ordinary Python class/field semantics.
class mpz:
    def __init__(self, value: int) -> None:
        self._handle = value

    def __str__(self) -> str:
        return str(self._handle)
