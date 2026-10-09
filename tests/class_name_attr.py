# C.__name__ is the class's name, also as cls.__name__ in a class method (and in the copy of it
# that an exception class inherits, see exc_classmethod_inherit)
class C:
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @staticmethod
    def other() -> str:
        return C.__name__ + "!"


class Err(ValueError):
    @classmethod
    def describe(cls) -> str:
        return "<" + cls.__name__ + ">"


class Sub(Err):
    pass


print(C.name(), C.other(), C.__name__, Err.__name__, Sub.describe(), Err.describe())
print(f"{C.__name__}:{len(Sub.__name__)}")
