# error: syntax_param_line.py:4: error: parameter without a default follows parameter with a default
def f(a,
      b=1,
      c):
    pass


print("ran")
