# error: two builtin exception bases must be independent and have ordinary Exception behavior
class Bad(ValueError, AttributeError):
    pass
