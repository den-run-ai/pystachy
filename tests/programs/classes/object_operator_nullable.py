events: list[str] = []


class Value:
    def __init__(self, number: int):
        self.number = number

    def __eq__(self, other):
        events.append("eq")
        return self.number == other.number

    def __ne__(self, other):
        events.append("ne")
        return self.number != other.number

    def __lt__(self, other):
        events.append("lt")
        return self.number < other.number


def equal(left: Value, right: Value) -> bool:
    return left == right


def unequal(left: Value, right: Value) -> bool:
    return left != right


def less(left: Value, right: Value) -> bool:
    return left < right


one = Value(1)
same = Value(1)
two = Value(2)
print(equal(one, same), unequal(one, two), less(one, two))
print([one] == [same], [one] != [two], [one] < [two])
print(events)
events.clear()
print(equal(None, None), unequal(None, None))
for missing in [True, False]:
    try:
        print(equal(None if missing else one, one if missing else None))
    except AttributeError as error:
        print(type(error).__name__)
print(events)


class Aware:
    def __eq__(self, other):
        events.append("aware")
        return other is None


def nullable(left: Aware, right: Aware) -> bool:
    return left == right


aware = Aware()
events.clear()
print(nullable(aware, None), nullable(None, aware))
print(aware == None, None == aware, aware != None, None != aware)  # noqa: E711
print(events)
