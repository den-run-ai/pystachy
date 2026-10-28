# pystachy: dynamic-any
from typing import Any


def compare(label: str, left: Any, right: Any) -> None:
    print(label, type(left).__name__, type(right).__name__)
    print(type(left) is type(right), type(left) == type(right),
          type(left) is not type(right), type(left) != type(right))


# Typed iterators and dynamic runtime iterators retain different payload layouts,
# but their Python types agree. Keep both alive through allocations and reads.
items: list[Any] = [11, 12]
boxed_items: Any = items
left: Any = iter(items)
right: Any = iter(boxed_items)
for i in range(16):
    garbage = ["allocation " + str(i)]
compare("list", left, right)
print(next(left), next(right), next(left), next(right))
typed_iterator = iter(items)
print("mixed type", type(typed_iterator) is type(right),
      type(right) == type(typed_iterator), typed_iterator.__class__ is right.__class__)
compare("list layouts", iter([1, 2]), iter(["a", "b"]))

pair: tuple[Any, Any] = (21, 22)
boxed_pair: Any = pair
compare("tuple", iter(pair), iter(boxed_pair))
compare("tuple layouts", iter((1, 2)), iter(("a", "b")))

text = "ab"
boxed_text: Any = text
compare("string", iter(text), iter(boxed_text))

mapping: dict[Any, Any] = {"a": 31, "b": 32}
boxed_mapping: Any = mapping
compare("dict", iter(mapping), iter(boxed_mapping))
compare("dict keys", iter(mapping.keys()), iter(boxed_mapping))
compare("dict key layouts", iter({1: 2}), iter({"a": "b"}))
compare("dict value layouts", iter({1: 2}.values()), iter({"a": "b"}.values()))
compare("dict item layouts", iter({1: 2}.items()), iter({"a": "b"}.items()))
compare("set layouts", iter({1, 2}), iter({"a", "b"}))

numbers = range(3)
boxed_numbers: Any = numbers
compare("range", iter(numbers), iter(boxed_numbers))
compare("reverse range", iter(numbers), reversed(boxed_numbers))
compare("reverse sequence", reversed(boxed_pair), reversed(boxed_text))
compare("forward and reverse list", iter(items), reversed(boxed_items))
compare("reverse list and dict", reversed(boxed_items), reversed(boxed_mapping))
compare("reverse list and tuple", reversed(boxed_items), reversed(boxed_pair))
compare("forward list and tuple", iter(items), iter(boxed_pair))
compare("dict keys and values", iter(mapping.keys()), iter(mapping.values()))


# A user class with the same spelling is still a different Python type.
class list_iterator:
    def __iter__(self):
        return self

    def __next__(self) -> int:
        return 99


custom: Any = list_iterator()
compare("user name and typed", custom, iter(items))
compare("user name and dynamic", custom, iter(boxed_items))
print(next(custom))
