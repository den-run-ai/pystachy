# Making an exception does not format its arguments (CPython's str(e) and repr(e) format args
# when they run): where __init__ first assigns fields and then calls super().__init__(), no
# __repr__ or __str__ of the constructor's arguments runs as the object is made.
class Noisy:
    def __repr__(self) -> str:
        print("repr of Noisy")
        return "Noisy()"

    def __str__(self) -> str:
        print("str of Noisy")
        return "noisy"


class Wrapped(RuntimeError):
    def __init__(self, item: Noisy, note: str) -> None:
        self.item = item
        super().__init__(note)


class One(RuntimeError):
    def __init__(self, item: Noisy) -> None:
        self.item = item
        super().__init__("one")


w = Wrapped(Noisy(), "wrapped")
print("made")
print(str(w), repr(w))
o = One(Noisy())
print("made one")
print(str(o), repr(o))
