# Comparison contexts follow methods and wrappers without leaking into strict
# argument annotations or sharing a specialization with a different result mode.
def empty(n):
    return []


class Factory:
    def make(self, n):
        return [empty(n), [n]]

    def __call__(self, n):
        return [empty(n), [n]]


class Derived(Factory):
    pass


class Holder:
    def __init__(self, fn):
        self.fn = fn


factory = Derived()
bound = factory.make
holder = Holder(bound)
expected: list[list[str]] | float = [["x"]]
print(expected == factory.make(1), expected == bound(1), expected == holder.fn(1))
base: Factory = factory
print(expected == base.make(1), expected == factory(1))


def closure(offset):
    def make(n):
        return [empty(n + offset), [n]]
    return make


closed = closure(0)
print(expected == closed(1))


def fresh(n):
    return [n]


def accept(values: list[int | float]) -> int:
    item = values[0]
    if isinstance(item, int):
        return item
    return 0


def compared(n):
    print("body", accept(fresh(n)))
    return [n]


words: list[str] | float = ["x"]
print(words == compared(9007199254740993))
print(words == compared(accept(fresh(9007199254740993))))


def rows(n):
    return [empty(n), [n]]


def reverse(n):
    return [empty(n), [n]]


# Both uses supply exactly the same full union context and argument type.
# Only the strict result stores boxed int|str items; mutate both child lists.
union_rows: list[list[int | str]] | float = [[1]]


def check_modes() -> None:
    print("soft-first", union_rows == rows(1))
    required: list[list[int | str]] | float = rows(1)
    if isinstance(required, list):
        required[0].append("strict-a")
        required[1].append("strict-b")
    print(required)
    other: list[list[int | str]] | float = reverse(2)
    if isinstance(other, list):
        other[0].append("strict-c")
        other[1].append("strict-d")
    print(other)
    print("strict-first", union_rows == reverse(2))


check_modes()

# Builtin copies forward result hints without making their input calls strict.
copy = list
print(expected == list(rows(1)), expected == sorted(rows(1)), expected == copy(rows(1)))


def mapping(n):
    return {"x": rows(n)}


mapped: dict[str, list[list[str]]] | float = {"x": [["x"]]}
print(mapped == dict(mapping(1)))

# Comprehension result hints survive nested template compilation, while the
# annotated argument inside each result call still uses its strict context.
numbers: list[int] = [1, 2]
number_set: set[int] = {1, 2}
print(numbers == [accept(fresh(n)) for n in [1, 2]])
print(number_set == {accept(fresh(n)) for n in [1, 2]})
print(numbers == list(accept(fresh(n)) for n in [1, 2]))
