# error: dict_merge_kwargs_dict.py:5: error: ** of a dict[str,int] in a dict display is not supported: of a function's **kwargs (with str keys), or of dicts of one type, it is
# A display merges **kwargs records into a record, or dicts of one type into a dict, not both
def f(**kw):
    d = {"a": 1}
    return {**kw, **d}


print(f(b=2))
