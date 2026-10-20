# error: exc_classvar_cls_inherited.py:7: error: assigning class attribute 'made' through S (cls in class method create(), which S inherits), which inherits it from E, is not supported
class E(Exception):
    made = 0

    @classmethod
    def create(cls, msg: str) -> "E":
        cls.made += 1
        return cls(msg)


class S(E):
    pass


a = E.create("a")
b = S.create("b")
print(E.made, S.made)  # (CPython: 1 2: S.create() gives S its own made, E's 1 plus 1)
