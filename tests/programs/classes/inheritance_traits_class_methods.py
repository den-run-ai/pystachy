# A trait's class method that overrides one the primary chain's class inherits comes first, as in
# CPython's method resolution order (Both, Primary, Trait, Root), also where the inherited one
# uses cls (inherit copies it for each class); one the class defines itself comes before both.
class Root:
    @classmethod
    def f(cls) -> str:
        return cls.__name__


class Primary(Root):
    pass


class Trait(Root):
    @classmethod
    def f(cls) -> str:
        return "trait"


class Both(Primary, Trait):
    pass




class Own(Primary, Trait):
    @classmethod
    def f(cls) -> str:
        return "own"


class Plain(Primary):
    pass


print(Both.f(), Own.f(), Plain.f(), Both().f())
