# pystachy: python-int
# Identity where CPython's answer is decided: one object, None, a bool, unequal
# values, or equal values in CPython's small-int cache (-5 to 256).
x = 2 ** 70
y = x
print(x is y, int(x) is x, x is not y)
five = 5
total = 2 + 3
count = len("abcde")
print(five is total, five is not total, count is five, five is count)
low = -5
also_low = -(3 + 2)
top = 256
also_top = 255 + 1
print(low is also_low, top is also_top, low is not top)
missing: int | None = None
some: int | None = five
print(missing is None, some is not None, some is five, x is missing, missing is x)
other = 2 ** 71
flag = True
print(x is other, flag is five, five is flag, x is not other)
