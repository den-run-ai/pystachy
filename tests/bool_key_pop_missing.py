# d.pop(k) of a bool pops the int key it equals; a key the dict lacks raises CPython's KeyError,
# which names the bool: KeyError: False
d: dict[int, int] = {1: 1}
if True in d:
    d[1] = d[True] + 1
print(d, d.pop(True), d)
d[2] = 5
print(d.pop(False, -1), d)
x = d.pop(False)
