# error: class_local_base_method.py:10: error: local variable 'E' is read before its first assignment; declare it first (E: T)
# Base.__init__(self, ...) in a method of an exception class reads Base (class_local_call.py)
class E(Exception):
    def __init__(self, m: str) -> None:
        self.m = m


class F(E):
    def __init__(self, m: str) -> None:
        E.__init__(self, m)
        E = 5


print(F("x").m)
