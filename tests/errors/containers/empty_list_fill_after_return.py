# error: empty_list_fill_after_return.py:6: error: cannot infer the type of 'xs'
# For f("s") the code after the return does not run, so its append does not type xs (it made
# sum(xs) the float 0.0): xs is an empty list that nothing fills, which needs an annotation.
def f(x):
    xs = []
    print(sum(xs))
    if isinstance(x, str):
        return 0
    xs.append(1.5)
    return len(xs)


print(f("s"))
