# An unused inherited method's implicit cls is never a read of the module global cls.
class Base(Exception):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

class Sub(Base):
    pass

cls = [1]
try:
    raise ValueError('caught')
except ValueError as cls:
    print(cls)
print('ok')
