# error: optional_subclass_error.py:18: error: unsupported operand type(s) for +: 'int' and 'str'
# The statements after the import keep the except clause (#1504), and the program does not
# compile with it: it is compiled again as before, which reports the error once.
class Missing(ImportError):
    pass


def need() -> int:
    raise Missing("unavailable")


try:
    import json

    v = need()
except ImportError:
    v = 0
print(json.dumps(v + "a"))
