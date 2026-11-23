# a search of a list of values of object: each item is compared as CPython compares it, by
# identity, then == of what it holds (object_containers_eq.py)
xs: list[object] = [1, "a"]
print("a" in xs, 1.0 in xs, "b" in xs)
