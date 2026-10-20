# Calls of functions that return None, used where a value is expected: a comprehension run
# for its effects, comparisons with None.
def f() -> None:
    print("in f")


xs: list[int] = []
[print(x) for x in range(3)]
[xs.append(i) for i in range(4)]
print(xs)
if f() is None:
    print("none")
print(f() is not None)
print(f() is None, f() == None, f() != None)
print(sum((x for x in [1, 2]), 10), sum(x for x in [1, 2]))
