from typing import Generic, TypeVar
from adapter import TypedIterable, TypedIterator, typed_iterable, typed_iterator
from lookup import TypedLookup, dict_lookup, index_lookup
from fixed_interfaces import PairCursor, read_pair
from fixed_tuple_lists import first, made

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value: T = value

    def read(self) -> T:
        return self.value


# This helper keeps checked annotations even when the entry module opts in.
# Merely retaining its tuple in an ordinary generic object must not copy it.
checked = first(made())
assert checked == (1, -9223372036854775808)
assert Box(checked).read() is checked
nested_checked = (checked, "kept")
assert Box(nested_checked).read() is nested_checked
print("ordinary generic tuple identity preserved")

inferred = typed_iterator(PairCursor(checked))
assert next(inferred) is checked
assert read_pair(typed_iterator(PairCursor(checked))) is checked
print("inferred and checked-consumer iterator views preserved")

pairs: TypedIterator[tuple[int, int]] = typed_iterator([checked, (2, 3)])
assert list(pairs) == [checked, (2, 3)]
nested: TypedIterator[tuple[tuple[int, int], str]] = typed_iterator([nested_checked])
assert list(nested) == [nested_checked]
optional_values: list[int | None] = [None, 7]
optional: TypedIterator[int | None] = typed_iterator(optional_values)
assert list(optional) == optional_values
optional_pairs: list[tuple[int | None, str]] = [(None, "none"), (7, "seven")]
optional_items: TypedIterator[tuple[int | None, str]] = typed_iterator(optional_pairs)
assert list(optional_items) == optional_pairs
print("lexical iterator tuple and optional views agree")

sources: list[TypedIterable[tuple[int, int]]] = [
    typed_iterable([checked]), typed_iterable(((2, 3),)),
]
assert [list(source) for source in sources] == [[checked], [(2, 3)]]
assert [list(source) for source in sources] == [[checked], [(2, 3)]]
dictionary = {0: checked}
sequence = [checked]
lookups: list[TypedLookup[int, tuple[int, int]]] = [dict_lookup(dictionary), index_lookup(sequence)]
assert [source[0] for source in lookups] == [checked, checked]
dictionary[0] = (4, 5)
sequence[0] = (6, 7)
assert [source[0] for source in lookups] == [(4, 5), (6, 7)]
print("nested iterable and lookup interfaces share views")
