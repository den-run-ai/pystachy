# pystachy: dynamic-any
# A display whose items hold an empty list or dict, in a module that compiles typing.Any as dynamic
# values: the items before it give its type, as in modules that do not opt in, or, where the items
# have no one type, it holds Any values (#782, #777).
pairs = [([7], 2), ([], 3), ([1, 2], 4)]
print(pairs, len(pairs[1][0]))
data = [{"a": 1, "items": [1]}, {"a": 1.5, "items": []}]
print(data)
data[1]["items"].append("x")
print(data[1])
