# A tuple of variable length is sliced by bounds known at run time, into a tuple[int, ...]
# (#480 rejected it; #473's stepped slices support it)
def tail(v: tuple[int, ...]) -> tuple[int, ...]:
    return v[1:]


print(tail((1, 2, 3)))
