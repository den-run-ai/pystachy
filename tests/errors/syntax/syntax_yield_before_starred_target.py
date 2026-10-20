# error: syntax_yield_before_starred_target.py:4: error: 'yield' outside function
# (CPython compiles the value before the targets)
print("ran")
*a = yield
