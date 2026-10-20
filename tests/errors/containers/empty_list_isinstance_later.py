# error: empty_list_isinstance_later.py:7: error: cannot infer the type of 'xs', an empty list so far
# The fill is in a branch of isinstance() of a local assigned after the read, whose type is not
# known there: f(3) never appends, so CPython's sum is the int 0. (The fill made the list a
# list[float], and the sum 0.0.)
def f(a):
    xs = []
    print(sum(xs))
    y = a
    if isinstance(y, str):
        xs.append(1.5)
    return len(xs)


print(f(3))
