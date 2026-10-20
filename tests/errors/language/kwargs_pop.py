# error: kwargs_pop.py:3: error: changing **kwargs is not supported: copy it to a dict first (d = dict(kwargs))
def f(**kwargs):
    verbose = kwargs.pop("verbose", False)
    return verbose


print(f(verbose=True))
