class Number:
    def __add__(self, other):
        return other + 1


class Text:
    def __add__(self, other):
        return other + "!"


def add_number(value: Number, other: int | None):
    return value + other


def add_text(value: Text, other: str | None):
    return value + other


number = Number()
print(add_number(number, 1))
try:
    print(add_number(number, None))
except TypeError:
    print("numeric TypeError")

text = Text()
print(add_text(text, "ok"))
try:
    print(add_text(text, None))
except TypeError:
    print("string TypeError")
