# Closed builtin comparisons read each operand with its own layout.
a: list[int] = []
b: list[str] = []
print(a == b, a != b)
a.append(3)
b.append("3")
print(a == b, a != b)
a.clear()
b.clear()
print(a == b)

x = [[1], []]
y = [(1,), (2,)]
print(x == y)
x.clear()
y.clear()
print(x == y)

ints: dict[int, list[int]] = {}
words: dict[str, list[str]] = {}
print(ints == words)
ints[1] = [2]
words["1"] = ["2"]
print(ints == words)

left = {1: [True, False]}
right = {1: [1.0, 0.0]}
print(left == right)
print(left, right)

print((1, "x") == (1.0, 2))
print((1, "x") == (1.0,))
print([1] == (1,))
print(1 == "1", None == 1)

optional: list[int | None] = [None, 2]
plain: list[int] = [0, 2]
print(optional == plain)
optional[0] = 0
print(optional == plain)

nan = float("nan")
nans = [nan]
nums = [0]
print(nans == nums, nums == nans)
print([-0.0] == [0], [True] == [1.0])
# Larger than double's exact integer range: never round before comparing.
print([9007199254740993] == [9007199254740992.0])
