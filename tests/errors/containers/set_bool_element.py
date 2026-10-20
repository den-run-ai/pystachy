# error: set_bool_element.py:3: error: a bool element is added to a set of int elements, where CPython keeps an element it adds as the bool it is (True, not 1): convert the bool with int()
s = {1, 2}
s.add(True)  # (CPython: {1, 2}, but {0} | {False} keeps 0, and {False} | {0} keeps False)
print(s)
