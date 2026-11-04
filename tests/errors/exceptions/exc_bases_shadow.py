# error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base
IndexError = 42


class Bad(ValueError, IndexError):
    pass
