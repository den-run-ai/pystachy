import inspect
default: object = inspect.Parameter.empty
default = 5
p = inspect.Parameter("x", inspect.Parameter.KEYWORD_ONLY, default=default)
print(p)
