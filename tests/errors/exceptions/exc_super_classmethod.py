# error: exc_super_classmethod.py:6: error: super() in a class method (which binds cls, the class) or a static method without parameters is not supported
class E(ValueError):
    @classmethod
    def show(cls, e: "E") -> str:
        # super() binds cls, not e: CPython raises TypeError (BaseException.__str__ needs an object)
        return super().__str__()


print(E.show(E("hi")))
