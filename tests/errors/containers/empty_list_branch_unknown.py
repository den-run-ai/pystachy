# error: empty_list_branch_unknown.py:7: error: cannot infer the type of 'xs', an empty list so far
# An empty list read before the if that fills it, whose test the types decide only once x has
# the value given after the read: which branch runs is not known where the list is printed.
# (Taking the first fill, "none", gave an error about the int that the else branch appends.)
def collect(x):
    xs = []
    print(xs, len(xs))
    x = 5
    if x is None:
        xs.append("none")
    else:
        xs.append(10)
    return xs


print(collect(None))
