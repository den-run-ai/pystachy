from decimal import Decimal


class Match:
    def __eq__(self, other: Decimal) -> bool:
        print("eq")
        return other == Decimal("2")

    def __lt__(self, other: Decimal) -> bool:
        print("lt")
        return other == Decimal("2")

    def __le__(self, other: Decimal) -> bool:
        print("le")
        return other == Decimal("2")

    def __gt__(self, other: Decimal) -> bool:
        print("gt")
        return other == Decimal("2")

    def __ge__(self, other: Decimal) -> bool:
        print("ge")
        return other == Decimal("2")


value = Decimal("2")
match = Match()
print(value == match, match == value, value != match, match != value)
print(value < match, value <= match, value > match, value >= match)
print(match in (value,), value in (match,), (value, value).count(match))
print((value,).index(match))
print(value == None, None == value)
for symbol in ["<", "<=", ">", ">="]:
    try:
        if symbol == "<":
            print(value < None)
        elif symbol == "<=":
            print(value <= None)
        elif symbol == ">":
            print(value > None)
        else:
            print(value >= None)
    except TypeError as error:
        print(error)
