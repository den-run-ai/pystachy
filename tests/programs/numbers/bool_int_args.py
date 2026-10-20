# a bool is an int where an index, a count or a start is expected
xs = [10, 20, 30]
print(xs.pop(True))
xs.insert(True, 9)
print(xs, "abc".find("c", True), "abcabc".rfind("b", False, True + 2))
for i, x in enumerate(["a"], True):
    print(i, x)
for i, x in enumerate(["b"], start=False):
    print(i, x)
t = (1, "two")
print(t[True], t[False])
print(xs.index(9, True), "a,b,c".split(",", True))
