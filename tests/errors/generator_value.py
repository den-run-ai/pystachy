# error: a generator expression is only supported as the argument of sum()
g = (x for x in [1, 2])
print(sum(g), sum(g))
