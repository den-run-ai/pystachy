# error: get() returns both bytes and str (each function has one return type) (compiling Base.get(bool) for the call at tests/errors/inference/select_result_overridden.py:16)
# A method of a class in a hierarchy keeps one return type: a call dispatches on the object's class.
class Base:
    def get(self, raw: bool = False):
        if raw:
            return b"x"
        return "x"


class Sub(Base):
    def get(self, raw: bool = False):
        return "y"


def show(o: Base) -> None:
    print(o.get())


show(Base())
show(Sub())
