# A class object of a class whose __init__ takes an int, called with a str: no function makes its
# objects from a str (its __init__ would get another type than it takes), so the call raises
# TypeError, where CPython makes the object (its __init__ keeps the str). The class's calls with
# what its __init__ takes, and other classes' calls with a str, make their objects.


class Coded(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"code {code}")
        self.code = code


def make(c: type[Exception], arg: str) -> None:
    try:
        raise c(arg)
    except Coded as e:
        print("coded", e.code)
    except Exception as e:
        print(type(e).__name__, e)


make(ValueError, "x")
make(Coded, "x")
cls = Coded
print(repr(cls(5)))
