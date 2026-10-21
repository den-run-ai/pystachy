from collections.abc import Sequence


def items(count: int) -> tuple[int, ...]:
    return tuple([i for i in range(count)])


def empty() -> tuple[int, ...] | None:
    return tuple([])


for count in [0, 1, 3, 12]:
    values = items(count)
    copied = tuple(values)
    print("identity", copied is values)
    print("type", isinstance(values, tuple), isinstance(values, Sequence))
    print("truth", bool(values), not values)
    print("list", list(values))
    print("ordering", values < items(count + 1), values > items(count + 1))
    print("ordering-equal", values <= items(count), values >= items(count))
    print("literal", values == (), () == values, values != (0,), (0,) != values)
    print("format", f"values={values}")
    for i, value in enumerate(values):
        print("enumerate", i, value)
    for value in reversed(values):
        print("reversed", value)
    for a, b in zip(values, values):
        print("zip", a, b)
    fresh: tuple[int, ...] = tuple()
    literal: tuple[int, ...] = ()
    print("empty", fresh, literal, empty())

print("optional", tuple([1, None, 3]))
print("text", tuple("abc"))
