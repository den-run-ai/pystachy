# error: kwargs_change.py:3: error: changing **kwargs is not supported: copy it to a dict first (d = dict(kwargs))
def f(**kwargs):
    kwargs["extra"] = 1
    return kwargs


print(f(a=1))
