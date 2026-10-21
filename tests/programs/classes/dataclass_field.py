# dataclasses.field(): defaults, default factories (called for each object, in field order),
# init=False, repr=False, compare=False and keyword-only fields, also after KW_ONLY.
import dataclasses
from dataclasses import KW_ONLY, dataclass, field


def numbered() -> list[int]:
    print("numbered")
    return [1, 2, 3]


def label(text: str) -> str:
    print("label", text)
    return text


class Tally:
    def __init__(self) -> None:
        print("Tally()")
        self.n = 0


@dataclass
class Order:
    customer: str
    items: list[str] = field(default_factory=list)
    numbers: list[int] = field(default_factory=numbered)
    prices: dict[str, float] = dataclasses.field(default_factory=dict)
    tally: Tally = field(default_factory=Tally, repr=False, compare=False)
    note: str = field(default=label("default note"))
    pairs: list[tuple[int, str]] = field(default_factory=lambda: [(1, "ä")])
    total: float = field(init=False, default=0.0)
    lines: list[str] = field(init=False, default_factory=lambda: ["header"])
    audit: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        print("post_init", self.customer)
        self.total = sum(self.prices.values(), 0.0)
        self.audit = "checked " + self.customer


print("class created")
a = Order("Ada")
b = Order("Bo", ["pen"], prices={"pen": 1.5}, note="é")
print(a)
print(b)
a.items.append("ink")
a.lines.append("body")
print(a.items, b.items, a.lines, b.lines, a.items is b.items)
print(a.total, b.total, a.audit, b.audit)
print(a == Order("Ada"), a == b)
c = Order("Ada")
c.tally.n = 5
c.items.append("ink")
c.lines.append("other")
print(a == c, a.tally.n, c.tally.n)


@dataclass
class Account:
    owner: str
    _: KW_ONLY
    balance: int = 0
    currency: str = field(default="EUR", kw_only=False)
    tags: list[str] = field(default_factory=list)


@dataclass
class Mixed:
    x: int
    y: int = field(kw_only=True)
    z: int = 3


acct = Account("Zoë", "USD", balance=10)
print(acct, Account("Al", tags=["a"]))
print(Mixed(1, y=2), Mixed(1, 4, y=0))


@dataclass
class Lazy:
    name: str
    cache: dict[str, int] = field(init=False)

    def fill(self) -> None:
        self.cache = {self.name: len(self.name)}


lz = Lazy("lazy")
try:
    print(lz.cache)
except AttributeError as e:
    print("AttributeError", e)
lz.fill()
print(lz.cache, lz)


def build(n: int) -> list[Order]:
    out: list[Order] = []
    for i in range(n):
        out.append(Order(f"c{i}", numbers=[i]))
    return out


orders = build(2)
print([o.numbers for o in orders], [o.items for o in orders])
