# error: exc_classmethod_dispatch.py:17: error: calling class method k() on an object of E, which may be one of S, is not supported: it uses cls, which would be E (calls are not dispatched on the object's class; call E.k() or S.k())
class E(Exception):
    kind = "E"

    @classmethod
    def k(cls) -> str:
        return cls.kind


class S(E):
    kind = "S"


try:
    raise S("boom")
except E as e:
    print(e.k())  # (CPython: S)
