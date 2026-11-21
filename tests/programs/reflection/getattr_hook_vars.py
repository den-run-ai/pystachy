# __getattr__ (#1536) answers attribute reads, not the instance __dict__: vars() and dir() list
# what the object holds, an unassigned field is no key of vars(), and a format that reads one
# raises KeyError without asking the method.
class Card:
    def __init__(self, full: bool) -> None:
        self.suit = "hearts"
        if full:
            self.label = "queen"

    def __getattr__(self, name: str) -> str:
        return "hook " + name


for c in [Card(True), Card(False)]:
    print(vars(c), sorted(dir(c))[-3:], "__getattr__" in dir(c))
    print(c.label, c.zz, c.suit)
    for k, v in vars(c).items():
        print(k, v)
    for k in vars(c).keys():
        print("key", k)
    print(dict(vars(c)), "%(suit)s" % vars(c))
    try:
        print("{label}".format_map(vars(c)))
    except KeyError as e:
        print("KeyError:", e)
