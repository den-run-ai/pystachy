# A submodule whose code defines a variable, a class, an exception class and a function, then
# raises: no import of it binds a name (tests/programs/exceptions/exc_import_failed_names.py)
X = 5


class Made:
    k: int = 3

    @staticmethod
    def sm() -> int:
        return 4


class MadeError(Exception):
    pass


def fn() -> int:
    return 7


raise ValueError("made raises after its definitions")
