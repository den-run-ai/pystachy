# A bool where an int index, slice bound or range() argument goes; int()/float() of Unicode
# digits and spaces; input() of a non-str prompt.
xs = [10, 20, 30]
b = True
print(xs[b], xs[False], "abc"[True], xs[True:], list(range(True, 3)))
xs[b] = 5
print(xs, int("\u0663\u0664"), int("\u3000 12 \u2003"), float("\u0661.\u0665"), int("\uff11\uff12"), float(" 1e3\u00a0"))
print(input(5))
