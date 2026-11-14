# Results that every return gives one constant (constargs, docs/typed-ir.md), alone or as an
# item of the tuple a function makes: the caller's tests of them are decided, until a
# return that can run gives another.


class Rules:
    def __init__(self) -> None:
        self.active: Rules | None = None  # nothing assigns it again

    def resolve(self, key: str | None) -> tuple["Rules | None", str | None]:
        rules = self.active if self.active is not None and key is not None else None
        if rules is None:
            return None, key
        return rules, key.upper()

    def apply(self, key: str | None = None) -> str:
        rules, key = self.resolve(key)
        if rules is not None:
            return "ruled " + str(key)
        return "plain " + str(key)


def lookup(name: str, strict: bool = False) -> tuple[bool, int]:
    if strict and not name:
        raise ValueError("empty name")
    if name == "one":
        return True, 1
    return False, 0


def never(name: str) -> None:
    return None


def sometimes(name: str) -> str | None:
    if name == "x":
        return "found " + name
    return None


def first(name: str) -> int:
    found, value = lookup(name)
    if found:
        return value
    return -1


def main() -> None:
    r = Rules()
    print(r.apply(), r.apply("k"))
    print(first("one"), first("two"))
    for name in ["x", "y"]:
        if never(name) is not None:
            print("never has", name)
        got = sometimes(name)
        if got is not None:
            print(got)
        else:
            print("nothing for", name)
    try:
        lookup("", True)
    except ValueError as e:
        print(e)


main()
