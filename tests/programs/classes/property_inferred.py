# A property getter without a return annotation: its type is inferred from its return
# statements, as a method's is. Reads run the getter each time, in CPython's order.
class Account:
    def __init__(self, owner: str, cents: int) -> None:
        self.owner = owner
        self._cents = cents
        self.reads = 0
        self.tags: list[str] = []

    @property
    def cents(self):
        return self._cents

    @cents.setter
    def cents(self, v: int) -> None:
        self._cents = v

    @property
    def dollars(self):
        return self._cents / 100

    @property
    def rich(self):
        return self._cents >= 100000

    @property
    def label(self):
        return f"{self.owner}: {self.dollars:.2f}"

    @property
    def parts(self):
        return (self.owner, self._cents)

    @property
    def history(self):
        return [self._cents, self._cents * 2]

    @property
    def table(self):
        return {self.owner: self.history}

    @property
    def counted(self):
        self.reads += 1
        return self.reads

    @property
    def nothing(self):
        self.reads += 10

    @property
    def first_tag(self):
        if len(self.tags) == 0:
            return None
        return self.tags[0]

    @property
    def me(self):
        return self

    @property
    def plus(self):
        return lambda n: n + self._cents


a = Account("ann", 12345)
print(a.cents, a.dollars, a.rich, a.label)
print(a.parts, a.history, a.table)
print(a.parts[0].upper(), sum(a.history), len(a.table))
a.cents = 200000
a.cents += 5
print(a.cents, a.rich, a.label)
print(a.counted, a.counted, a.me.counted, a.reads)
print(a.nothing, a.reads)
print(a.first_tag)
a.tags.append("vip")
t = a.first_tag
if t is not None:
    print(t.upper())
print(a.plus(1), a.me.me.owner)
print(getattr(a, "cents"), [x.cents for x in [a, Account("bob", 7)]])
print(sorted([Account("c", 3), Account("d", 1)], key=lambda x: x.cents)[0].owner)
while a.counted < 8:
    pass
print(a.reads)
