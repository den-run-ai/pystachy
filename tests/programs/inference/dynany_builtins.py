# pystachy: dynamic-any
# Comprehensions, sorted(), min(), max(), sum(), str.join(), dict and list methods and
# formatting over Any values.
from typing import Any

data: Any = [3, 1.5, 2, -4, 0.25]
print([x * 2 for x in data])
print([x for x in data if x > 1])
pairs: Any = {"a": 1, "b": "two", "c": [3]}
print({k: v for k, v in pairs.items()})
print([k for k in pairs])
print(list(pairs.keys()), list(pairs.values()))
print(sorted(data), sorted(data, reverse=True))
print(min(data), max(data), sum(data))
words: Any = ["pear", "fig", "apple"]
print(sorted(words), max(words), min(words), len(words))
print(", ".join(words), "-".join(sorted(words)))
nums: list[Any] = [5, 3, 9]
nums.sort()
print(nums, nums.index(9), nums.count(3))
nums.reverse()
print(nums, nums.copy(), nums.pop(0), nums)
d: dict[Any, Any] = {"x": 1}
d.update({"y": 2, 3: "z"})
print(d, d.setdefault("w", []), d)
print(d.pop("x"), d.pop("nope", "default"), d)
print(list(enumerate(words)))
for i, w in enumerate(words):
    print(i, w)
for a, b in zip(words, nums):
    print(a, b)
print("%s and %r" % (words[0], words[1]))
print("{} {}".format(words[0], nums[0]))
print(f"{words[2]:>8}|{nums[0]:03d}|{data[1]:.2f}")
v: Any = 255
print(f"{v:x} {v:b}", str(v).zfill(5), abs(-3))
s: Any = "a,b,,c"
parts = s.split(",")
print(parts, len(parts), [p for p in parts if p])
nested: Any = [[1, [2, 3]], {"k": (4, 5)}]
print(nested[0][1][0], nested[1]["k"][1])
flat: list[Any] = []
for x in nested[0]:
    if isinstance(x, list):
        for y in x:
            flat.append(y)
    else:
        flat.append(x)
print(flat)
total: Any = 0
for x in flat:
    total += x
print(total)
