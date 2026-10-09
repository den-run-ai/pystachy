# error: syntax_blocks_typevar_bound.py:8: error: too many statically nested blocks
# a type parameter's bound (and its default) is compiled as a function of its own, also where
# the def's annotations name the type parameter (which Pystachy leaves out of its signature)
def first[T](xs: list[T]) -> T:
    return xs[0]


def deep[T: [[[[[[[[[[[[[[[[[[[[[[0 for x0 in y] for x1 in y] for x2 in y] for x3 in y] for x4 in y] for x5 in y] for x6 in y] for x7 in y] for x8 in y] for x9 in y] for x10 in y] for x11 in y] for x12 in y] for x13 in y] for x14 in y] for x15 in y] for x16 in y] for x17 in y] for x18 in y] for x19 in y] for x20 in y] for x21 in y]](x: T) -> T:
    return x


print(first([1, 2]))
