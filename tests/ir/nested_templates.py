# Nested template instances: templates that call templates, so compiling one instance
# instantiates others, for several argument types and from inside another instance.
def first(xs):
    return xs[0]


def last(xs):
    return xs[len(xs) - 1]


def ends(xs):
    return [first(xs), last(xs)]


def both(a, b):
    return first(ends(a)) + last(ends(b))


def depth(x, n):
    if n == 0:
        return x
    return depth(x, n - 1)


print(both([1, 2, 3], [4, 5]))
print(both(["a", "b"], ["c"]))
print(both([1.5], [2.25, 3.0]))
print(depth("s", 3), depth(7, 2), ends(ends([9, 8, 7])))
