from mods.constructor_hierarchy import Total, Bonus


def inspect(value: Total) -> None:
    # Class checks need a declaration before any construction of that subclass.
    print(isinstance(value, Bonus), type(value) is Bonus, Bonus is type(value))


inspect(Total([1]))
inspect(Bonus((2, 3)))
