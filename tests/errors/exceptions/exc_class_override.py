# error: method 'describe' of 'Sub' overrides that of 'Base': only __init__, __str__ and __repr__ may be overridden
class Base(Exception):
    def describe(self) -> str:
        return "base"


class Sub(Base):
    def describe(self) -> str:
        return "sub"


print(Sub().describe())
