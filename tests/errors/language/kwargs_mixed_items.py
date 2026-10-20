# error: kwargs_mixed_items.py:3: error: using **kwargs(a=int, b=str) as a dict is not supported: its values have different types (read each by its name, kwargs['name'], or forward it, f(**kwargs))
def f(**kw):
    return list(kw.items())


print(f(a=1, b="x"))
