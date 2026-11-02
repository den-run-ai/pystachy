# An __init__ that raises before it calls super().__init__() makes no object: the call of the
# class raises that exception. One that gets to the call keeps that call's arguments.
class Checked(ValueError):
    def __init__(self, n: int, label: str) -> None:
        self.n = n
        if n < 0:
            raise TypeError("negative: " + str(n))
        self.label = label
        super().__init__(label + "=" + str(n))


try:
    Checked(-1, "bad")
except TypeError as t:
    print("TypeError", t)
c = Checked(4, "four")
print(str(c), repr(c), c.n, c.label)
try:
    raise Checked(-2, "worse")
except TypeError as t:
    print("TypeError", t)
except ValueError as v:
    print("ValueError", v)
