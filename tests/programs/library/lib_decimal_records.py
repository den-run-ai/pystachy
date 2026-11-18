# Decimals as typed program data: dataclass and class fields, list and dict items, dict keys,
# optional values, function parameters and results, sorting, and the usual money arithmetic.
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext

CENT = Decimal("0.01")


@dataclass
class Line:
    name: str
    price: Decimal
    quantity: int = 1
    discount: Decimal | None = None

    def total(self) -> Decimal:
        amount = self.price * self.quantity
        if self.discount is not None:
            amount -= amount * self.discount
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Invoice:
    lines: list[Line] = field(default_factory=list)
    rates: dict[str, Decimal] = field(default_factory=dict)

    def subtotal(self) -> Decimal:
        total = Decimal(0)
        for line in self.lines:
            total += line.total()
        return total

    def tax(self, region: str) -> Decimal:
        return (self.subtotal() * self.rates[region]).quantize(CENT, rounding=ROUND_HALF_UP)


class Account:
    def __init__(self, balance: Decimal) -> None:
        self.balance: Decimal = balance
        self.history: list[Decimal] = []

    def post(self, amount: Decimal) -> None:
        self.balance += amount
        self.history.append(amount)


def split(amount: Decimal, parts: int) -> list[Decimal]:
    share = (amount / parts).quantize(CENT, rounding=ROUND_FLOOR)
    shares = [share] * parts
    shares[0] += amount - share * parts
    return shares


def largest(values: list[Decimal]) -> Decimal | None:
    best: Decimal | None = None
    for value in values:
        if best is None or value > best:
            best = value
    return best


def seconds(text: str) -> tuple[int, int]:
    # an ISO 8601 seconds field, as isodate reads one: whole seconds and microseconds
    value = Decimal(text.replace(",", ".")).quantize(Decimal(".000001"), rounding=ROUND_FLOOR)
    microsecond = (value - int(value)) * 1000000
    return int(value), int(microsecond.to_integral())


invoice = Invoice(rates={"north": Decimal("0.0825"), "south": Decimal("0.07")})
invoice.lines.append(Line("widget", Decimal("19.99"), 3))
invoice.lines.append(Line("gadget", Decimal("4.995"), 10, Decimal("0.15")))
invoice.lines.append(Line("service", Decimal("120")))
print([str(line.total()) for line in invoice.lines], invoice.subtotal(), invoice.tax("north"), invoice.tax("south"))
print(invoice.lines[0], sorted(invoice.lines, key=lambda line: line.total())[0].name, max(line.price for line in invoice.lines))
account = Account(Decimal("100.00"))
for amount in split(Decimal("100.00"), 3):
    account.post(-amount)
print(account.balance, account.history, largest(account.history), largest([]), sum(len(str(a)) for a in account.history))
by_price: dict[Decimal, list[str]] = {}
for line in invoice.lines + [Line("spare", Decimal("19.990"))]:
    by_price.setdefault(line.price, []).append(line.name)
print(sorted(by_price.items()), Decimal("19.99") in by_price, Decimal("19.9900") in by_price, len({Decimal(1), Decimal("1.0"), Decimal("1.00")}))
print(seconds("59.999999999"), seconds("7,25"), seconds("0.0000004"), seconds("30"))
with localcontext() as context:
    context.prec = 6
    rate = Decimal(1) + Decimal("0.045") / 12
    balance = Decimal(1000)
    for month in range(12):
        balance = balance * rate
    print(balance, balance.quantize(CENT), rate ** 12, (rate ** 12 - 1).quantize(Decimal("0.0001")))
total = Decimal(0)
for text in ["0.1", "0.2", "0.3"]:
    total += Decimal(text)
print(total, total == Decimal("0.6"), 0.1 + 0.2 + 0.3 == 0.6, f"{total:.2f} {Decimal('1234567.891'):,.2f} {Decimal('0.125'):.1%}")
