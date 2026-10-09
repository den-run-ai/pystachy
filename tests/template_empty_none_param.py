# An empty list read before the code that fills it takes the type of its first fill, and a test
# that the argument types decide (y is None) leads only into the branch that runs. A parameter
# whose argument is None is None only until the function assigns it: x is still None where the
# list is printed, but not where it is filled, so it holds ints, not the else branch's str.
def collect(x, y):
    xs = []
    print(xs, len(xs))
    x = 5
    if x is not None:
        xs.append(10)
    else:
        xs.append("none")
    if y is None:
        xs.append(20)
    else:
        xs.append("y")
    return xs


print(collect(None, None))
print(collect(None, None)[1] + 1)
