# Stored interfaces keep several implementations behind fixed method signatures.
from adapter import TypedIterable, TypedIterator, typed_iterable, typed_iterator
from lookup import TypedLookup, dict_lookup, index_lookup


class Payload:
    def __init__(self, text: str) -> None:
        self.text = text


class ObservedSource:
    def __init__(self, values: list[int], events: list[str]) -> None:
        self.values = values
        self.events = events

    def __iter__(self):
        self.events.append("iter")
        return iter(self.values)


class SourceSlot:
    def __init__(self, source: TypedIterable[int]) -> None:
        self.source = source


def numbers():
    yield 4
    yield 5


def total(source: TypedIterable[int]) -> int:
    result = 0
    for value in source:
        result += value
    return result


def read_keys(source: TypedLookup[int, str], keys: list[int]) -> list[str]:
    return [source[key] if key in source else "missing" for key in keys]


def retained_words() -> TypedIterable[str]:
    words = ["kept", "alive"]
    return typed_iterable(words)


integers: list[TypedIterator[int]] = [typed_iterator([1, 2]), typed_iterator((3, 4))]
assert [list(stream) for stream in integers] == [[1, 2], [3, 4]]
words: TypedIterator[str] = typed_iterator(("red", "blue"))
assert list(words) == ["red", "blue"]
values: TypedIterator[float] = typed_iterator([1.5, 2.5])
assert list(values) == [1.5, 2.5]
pairs: TypedIterator[tuple[int, str]] = typed_iterator([(1, "one"), (2, "two")])
assert list(pairs) == [(1, "one"), (2, "two")]
mixed_values: list[int | str] = [7, "seven"]
mixed: TypedIterator[int | str] = typed_iterator(mixed_values)
assert list(mixed) == mixed_values
optional_values: list[int | None] = [None, 8]
optional: TypedIterator[int | None] = typed_iterator(optional_values)
assert list(optional) == optional_values
payload = Payload("before")
objects: TypedIterator[Payload] = typed_iterator([payload])
payload.text = "after"
item = next(objects)
assert item is payload and item.text == "after"
print("generic iterator items and reference identity ok")

sources: list[TypedIterable[int]] = [typed_iterable([1, 2]), typed_iterable((3, 4))]
assert [total(source) for source in sources] == [3, 7]
assert [total(source) for source in sources] == [3, 7]
slot = SourceSlot(sources[0])
assert total(slot.source) == 3
slot.source = sources[1]
assert total(slot.source) == 7
one_shot = typed_iterable(numbers())
assert total(one_shot) == 9 and total(one_shot) == 0
print("retained iterable replacement and repeatability ok")

events: list[str] = []
backing = [6]
observed = typed_iterable(ObservedSource(backing, events))
assert events == []
iterator = iter(observed)
assert events == ["iter"]
backing.append(7)
assert list(iterator) == [6, 7]
assert total(observed) == 13 and events == ["iter", "iter"]
print("deferred iter and live mutation ok")

dictionary = {0: "zero", 2: "two"}
sequence = ["first", "second"]
lookups: list[TypedLookup[int, str]] = [dict_lookup(dictionary), index_lookup(sequence)]
assert [read_keys(source, [-1, 0, 1, 2]) for source in lookups] == [
    ["missing", "zero", "missing", "two"],
    ["missing", "first", "second", "missing"],
]
dictionary[1] = "one"
sequence.append("third")
assert [len(source) for source in lookups] == [3, 3]
assert [read_keys(source, [1, 2]) for source in lookups] == [["one", "two"], ["second", "third"]]
for source in lookups:
    try:
        source[9]
        assert False
    except KeyError as error:
        assert str(error) == "9"
numeric: TypedLookup[str, int] = dict_lookup({"answer": 42})
assert numeric["answer"] == 42 and "answer" in numeric and len(numeric) == 1
print("shared multi-method lookups, mutation and exceptions ok")

kept: list[TypedIterable[str]] = [retained_words(), typed_iterable(("still", "here"))]
assert [list(source) for source in kept] == [["kept", "alive"], ["still", "here"]]
assert [list(source) for source in kept] == [["kept", "alive"], ["still", "here"]]
print("retained generic closures ok")
