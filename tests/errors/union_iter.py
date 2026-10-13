# error: union_iter.py:5: error: cannot iterate over list[int] | str: narrow it to one of its types first, with isinstance()
# a loop over a union, whose members' items differ
def f(x: list[int] | str) -> int:
    n = 0
    for c in x:
        n += 1
    return n


print(f([1]))
