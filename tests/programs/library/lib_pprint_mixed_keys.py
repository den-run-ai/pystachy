# pprint orders a dict's keys, and the items of a set it wraps, with <, and where < raises
# TypeError by the names of their types, as CPython's _safe_key does: None, "<class 'NoneType'>",
# before the strs and the ints, "<class 'str'>" and "<class 'int'>", each sorted.
import pprint

counts: dict[str | None, int] = {}
for tag in ["b", None, "a", "c", None]:
    counts[tag] = counts.get(tag, 0) + 1
print(pprint.pformat(counts))
pprint.pprint(counts, width=12)
print(pprint.saferepr(counts))
print(pprint.pformat(counts, sort_dicts=False))

numbers: dict[int | None, str] = {2: "a", None: "b", 1: "c"}
print(pprint.pformat(numbers))
print(pprint.pformat(numbers, width=8))

tags: set[str | None] = {"b", None, "a"}
print(pprint.pformat(tags, width=6))
