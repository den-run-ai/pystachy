# error: field 'code' of 'Base' declared again in 'Sub' (not supported, but for a class attribute of the same type)
class Base(Exception):
    code: int = 1


class Sub(Base):
    code: str = "two"


print(Sub().code)
