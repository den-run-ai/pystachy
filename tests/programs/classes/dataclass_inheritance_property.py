# Properties in a hierarchy of dataclasses: a subclass's @Base.x.setter, called through a
# base-typed object, and a frozen subclass's object as the default of another dataclass's field.
from dataclasses import dataclass, field


@dataclass
class Account:
    owner: str
    _cents: int = 0

    @property
    def balance(self) -> float:
        return self._cents / 100

    @balance.setter
    def balance(self, v: float) -> None:
        self._cents = round(v * 100)


@dataclass
class Savings(Account):
    rate: float = 0.01
    history: list[float] = field(default_factory=list)

    @Account.balance.setter
    def balance(self, v: float) -> None:
        self.history.append(v)
        self._cents = round(v * 100)


@dataclass(frozen=True)
class Origin:
    x: int = 0


@dataclass(frozen=True)
class Origin3(Origin):
    z: int = 0


@dataclass
class Scene:
    origin: Origin = Origin3(1, 2)
    accounts: list[Account] = field(default_factory=list)


accts: list[Account] = [Account("a"), Savings("b")]
for a in accts:
    a.balance = 12.5
    a.balance += 1
    print(a, a.balance)
s = Scene(accounts=accts)
print(s, s.origin == Origin3(1, 2), s.origin == Origin(1))
