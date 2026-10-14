# error: multiple inheritance is not supported: a class may have only one base
class Both(ValueError, KeyError):
    pass


raise Both("x")
