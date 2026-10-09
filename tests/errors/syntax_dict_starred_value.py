# error: syntax_dict_starred_value.py:3: error: cannot use a starred expression in a dictionary value
def f(a):
    return {1: *a}


print("ran")
