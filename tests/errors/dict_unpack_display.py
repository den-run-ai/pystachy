# error: dict displays with ** are not supported
a = {"x": 1}
b = {"y": 2}
c = {**a, **b}
print(c)
