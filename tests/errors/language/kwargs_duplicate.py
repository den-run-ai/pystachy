# error: kwargs_duplicate.py:6: error: __main__.h() got multiple values for keyword argument 'a'
def h(**kw):
    return kw


print(h(a=1, **{"a": 2}))
