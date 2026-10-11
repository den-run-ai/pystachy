# popitem() of an empty dict: CPython's KeyError, uncaught
d = {"a": 1}
print(d.popitem())
print(d.popitem())
