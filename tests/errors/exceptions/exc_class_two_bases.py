# error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base
class Both(ValueError, KeyError):
    pass


raise Both("x")
