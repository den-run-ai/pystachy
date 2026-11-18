# A union may hold a class's objects beside int, float, bool and str members: one tagged box,
# which isinstance() narrows to a member. Arguments, returns, locals, fields, list items, dict
# values, defaults and a mixed tuple's variable index hold one; a subclass is stored under its
# base member; None is a null box, as a class's own value may be None.
import sys
from dataclasses import dataclass
from typing import TextIO


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __repr__(self) -> str:
        return f"Money({self.cents})"

    def doubled(self) -> int:
        return 2 * self.cents


class Tip(Money):
    def doubled(self) -> int:
        return 3 * self.cents


class Label:
    def __init__(self, text: str) -> None:
        self.text = text


class Holder:
    def __init__(self, value: "int | Money") -> None:
        self.value = value


@dataclass
class Row:
    amount: "float | Money"
    name: str = "row"


def pick(n: int) -> "int | Money":
    if n % 2 == 0:
        return n
    return Money(n)


def cents(value: "int | Money") -> int:
    if isinstance(value, Money):
        return value.doubled()
    return value + 1


def cents_first(value: "int | Money") -> int:
    if isinstance(value, int):
        return value + 1
    return value.cents


def text(value: "str | Money") -> str:
    if isinstance(value, str):
        return value.upper()
    return repr(value)


def kind(value: "int | float | bool | str | Money | Label") -> str:
    if isinstance(value, Money):
        return "money"
    if isinstance(value, Label):
        return "label " + value.text
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "str " + value
    return "none"


def optional(value: "int | Money | None") -> str:
    if value is None:
        return "none"
    if isinstance(value, Money):
        return "money"
    return "int"


def widened(value: "int | Money") -> "int | str | Money":
    return value


def choose(n: int) -> "int | Money":
    return Money(n) if n > 2 else n


def with_default(value: "int | Money" = 5) -> str:
    if isinstance(value, Money):
        return "money"
    if isinstance(value, int):
        return "int " + str(value)
    return "none"


def write(out: "TextIO | str", line: str) -> str:
    if isinstance(out, str):
        return out + line
    out.write(line + "\n")
    return ""


def indexed(i: int) -> str:
    items = (1, Money(7), "s", 2.5)
    item = items[i]
    if isinstance(item, Money):
        return "money " + str(item.cents)
    return str(item)


def containers() -> None:
    values: list[int | Money] = [pick(i) for i in range(4)]
    values.append(Money(50))
    values.append(60)
    total = 0
    for value in values:
        if isinstance(value, Money):
            total += value.cents
        else:
            total += 100 * value
    print(total, len(values), cents(values[1]), cents(values[0]))
    by_name: dict[str, int | Money] = {"a": 1, "b": Money(2)}
    by_name["c"] = pick(3)
    for name in sorted(by_name):
        entry = by_name[name]
        if isinstance(entry, Money):
            print(name, "money", entry.cents)
        else:
            print(name, "int", entry)
    for holder in [Holder(Money(4)), Holder(4)]:
        held = holder.value
        print(cents(held), type(held).__name__)
    row = Row(Money(1))
    amount = row.amount
    print(isinstance(amount, Money), isinstance(Row(1.5).amount, float))
    copied = list(values)
    print(len(copied), copied[1] == values[1], copied[0] == values[0], copied[1] == values[3])


def none_object(flag: bool) -> "int | Money":
    missing: Money = Money(1) if flag else None
    return missing


print(cents(pick(1)), cents(pick(2)), cents(7), cents(Money(9)), cents(Tip(5)))
print(cents_first(pick(1)), cents_first(pick(2)))
print(text("q"), text(Money(3)))
print(kind(1), kind(2.5), kind(True), kind("s"), kind(Money(1)), kind(Label("l")), kind(Tip(1)))
print(optional(None), optional(pick(1)), optional(pick(2)))
print(isinstance(widened(pick(1)), Money), isinstance(widened(2), int))
print(isinstance(choose(3), Money), isinstance(choose(1), Money))
print(with_default(), with_default(Money(3)))
print(write("a", "b"), write(sys.stdout, "to stdout") == "")
print(indexed(0), indexed(1), indexed(2), indexed(3), indexed(-1))
containers()
absent = none_object(False)
print(absent is None, isinstance(absent, Money), isinstance(absent, int), optional(absent), with_default(absent))
