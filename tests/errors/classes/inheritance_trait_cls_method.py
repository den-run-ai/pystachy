# error: inheritance_trait_cls_method.py:24: error: class method 'f' of trait Trait uses cls where it overrides that of Root: not supported
# A trait's class method that overrides one of the primary chain's and uses cls would read the
# trait's class attributes through cls, where CPython's cls is the class that derives from both.
class Root:
    @classmethod
    def value(cls) -> int:
        return 0

    @classmethod
    def f(cls) -> int:
        return cls.value()


class Primary(Root):
    pass


class Trait(Root):
    @classmethod
    def f(cls) -> int:
        return cls.value() + 10


class Both(Primary, Trait):
    pass


print(Both.f())
