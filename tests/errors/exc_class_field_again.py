# error: field 'code' of 'Base' declared again in 'Sub' (not supported)
class Base(Exception):
    code: int = 1


class Sub(Base):
    code: int = 2


print(Sub().code)
