# error: syntax_unpacking_comprehension_line.py:5: error: iterable unpacking cannot be used in comprehension
# (the line of the *)
def f(x):
    return g(
        *a for a in x
    )


print("ran")
