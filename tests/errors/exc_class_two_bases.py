# error: an exception class with more than one base is not supported
class Both(ValueError, KeyError):
    pass


raise Both("x")
