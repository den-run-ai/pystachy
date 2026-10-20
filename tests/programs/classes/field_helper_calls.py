from mods.field_helpers import nested, optional, retain


class Holder:
    def __init__(self, value) -> None:
        self.first = retain(value)
        self.second = nested(value)
        self.defaulted = optional(value)
        self.explicit = optional(value, 9)


text = Holder("hello")
number = Holder(42)
items = [1, 2]
sequence = Holder(items)
print(text.first, text.second, text.defaulted, text.explicit)
print(number.first, number.second)
sequence.first.append(3)
print(sequence.first is items, sequence.second is items, items)


def helper(x, choose: bool):
    if choose:
        return x
    raise ValueError("helper failed")


class Checked:
    def __init__(self, value, choose: bool) -> None:
        self.value = helper(value, choose)


print(Checked("ok", True).value)
try:
    Checked("no", False)
except ValueError as e:
    print(e)
