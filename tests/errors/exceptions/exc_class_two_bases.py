# error: two builtin exception bases must be independent and have ordinary Exception behavior
class Both(ValueError, KeyError):
    pass


raise Both("x")
