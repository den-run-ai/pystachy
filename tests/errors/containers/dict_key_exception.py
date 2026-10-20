# error: dict_key_exception.py:7: error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not Oops (an exception object)
class Oops(Exception):
    pass


e = Oops()
seen: dict[Oops, int] = {e: 1}
