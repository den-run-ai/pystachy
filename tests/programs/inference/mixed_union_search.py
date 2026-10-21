"""Mixed-value search retains original container identity and current contents."""

items: list[int | str | list[int] | dict[str, int] | None] = [1, [1], {"n": 1}, "one", None, [1]]
query = [1.0]
mapping = {"n": 1.0}
print(query in items, mapping in items, items.count(query), items.index(mapping))
print(items.count([1.0]), items.index({"n": 1.0}), items.count([float(i) for i in [1]]))
print(items.index(query, 2, 6), query not in items)
items.remove([1.0])
items.remove({"n": 1.0})
print(items)
missing = [2.0]
try:
    print(items.index(missing))
except ValueError as error:
    print(str(error))

empty_items: list[list[int] | dict[str, int] | None] = [[], {}, [1], None]
print(empty_items.count([]), empty_items.index({}))
empty_items.remove([])
print(empty_items)
nested_empty: list[list[list[int]] | str] = [[[]]]
print(nested_empty.count([[]]))
optional_items: list[list[int | None] | str] = [[None]]
print(optional_items.count([None]))
try:
    items.remove(missing)
except ValueError as error:
    print(str(error))

original = [float("nan")]
def same(a: list[float] | str, b: list[float] | str) -> bool:
    return a == b

# Two fresh union boxes retain the same underlying mutable list identity.
boxed: list[list[float] | str] = [original, original]
print(same(original, original), original in boxed, boxed.count(original), boxed.index(original))
saved = boxed[0]
boxed[0] = "replaced"
for i in range(160):
    boxed.append(str(i) * 32)
print(saved in boxed)
original.append(7.0)
print(saved == boxed[1], boxed.count(original))

original_dict = {"nan": float("nan")}
def same_dict(a: dict[str, float] | str, b: dict[str, float] | str) -> bool:
    return a == b

dict_boxes: list[dict[str, float] | str] = [original_dict]
print(same_dict(original_dict, original_dict), original_dict in dict_boxes)

inner: list[int | str] = [1, "kept"]
outer: list[list[int | str] | int] = [inner, 4]
needle: list[float | str] = [1.0, "kept"]
print(needle in outer, outer.count(needle))
print(outer.count([1, "kept"]), outer.index([1, "kept"]))
inner[0] = 2
print(needle in outer, outer.count(needle))
print(outer.count([1.0]), outer.count([2.0]))

events: list[str] = []
def lhs() -> list[int] | str:
    events.append("left")
    return [1]

def rhs() -> list[float] | str:
    events.append("right")
    return [1.0]

print(lhs() == rhs(), events)
events.clear()

def receiver() -> list[list[int] | str]:
    events.append("receiver")
    return [[1]]

def failure() -> list[int] | str:
    events.append("failure")
    raise ValueError("needle failed")

try:
    print(receiver().index(failure()))
except ValueError as error:
    print(str(error), events)
