def make_strings(count: int) -> tuple[str, ...]:
    items: list[str] = ["value-" + str(i) for i in range(count)]
    result = tuple(items)
    items.clear()
    return result

def make_optional() -> tuple[str | None, ...]:
    items: list[str | None] = ["first", None, "last"]
    result = tuple(items)
    alias = items
    alias[0] = None
    alias[1] = "changed"
    alias.clear()
    return result

strings = make_strings(10)
optional = make_optional()
numbers: list[float] = [0.5, -1.5, 2.5]
numeric: tuple[float, ...] = tuple(numbers)
numbers[0] = 99.5
flags: list[bool] = [True, False]
booleans: tuple[bool, ...] = tuple(flags)
flags[0] = False
for i in range(100):
    garbage = [str(i) * 32, "temporary" + str(i)]
    garbage.append("another" + str(i))
print("strings", strings, repr(strings), len(strings))
print("optional", optional, repr(optional), len(optional))
print("numeric", numeric, repr(numeric), numeric[0], numeric[-1])
print("booleans", booleans, repr(booleans), booleans[0], booleans[-1])
for item in optional:
    if item is None:
        print("none")
    else:
        print("text", item)
print("saved", strings[0], strings[-1], optional[0], optional[-1])
