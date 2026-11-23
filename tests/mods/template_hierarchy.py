# A class template and its subclasses in an imported module (#962): each is compiled where the
# program uses it, its hierarchy requested then, as an imported subclass of a fixed layout's is.
class Event:
    def __init__(self, name, payload=None):
        self.name = name
        self.payload = payload

    def kind(self) -> str:
        return "event"

    def describe(self) -> str:
        return self.kind() + " " + self.name + " " + str(self.payload)


class Alarm(Event):
    def kind(self) -> str:
        return "alarm"


class Tick(Event):
    def __init__(self, n: int) -> None:
        super().__init__("tick", n)

    def kind(self) -> str:
        return "tick"


class Loose(Event):
    # (its own __init__ is a class template: each specialization derives from the one it makes)
    def __init__(self, payload):
        super().__init__("loose", payload)
