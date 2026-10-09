# error: syntax_future_in_function.py:3: error: from __future__ imports must occur at the beginning of the file
def f(x):
    from __future__ import annotations


print("ran")
