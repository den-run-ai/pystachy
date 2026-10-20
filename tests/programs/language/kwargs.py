# **kwargs: a function's extra keyword arguments, as each call passes them (a record of their names
# and types, as *args is a tuple of the extra positional ones). f(**kwargs) forwards them, and
# kwargs reads as the dict CPython makes: by name, get(), in, len(), iteration, keys(), and
# values(), items() and dict(kwargs) where its values share a type; it prints as that dict
def show(**kwargs):
    print(kwargs, len(kwargs), bool(kwargs), "a" in kwargs, "z" not in kwargs)
    for k in kwargs:
        print(" key", k)
    print(sorted(kwargs), list(kwargs.keys()), kwargs.get("a"), kwargs.get("z", 9))
    if "a" in kwargs:
        print("a is", kwargs["a"])


def target(x, y=0, *, label="none"):
    return f"{label}: {x + y}"


def wrap(f):
    def wrapper(*args, **kwargs):
        print("calling", f.__name__, args, kwargs)
        return f(*args, **kwargs)
    return wrapper


@wrap
def target2(x, y=0, *, label="none"):
    return f"{label}: {x + y}"


show()
show(a=1, b="two")
show(b=2.5)
print(target2(1), target2(1, y=2), target2(3, 4, label="sum"), target2(x=5, label="kw"))
print(target(**{"x": 1, "label": "lit"}))


def same(**kw):
    d = dict(kw)
    d["extra"] = 0
    return sorted(d.items()), list(kw.values())


print(same(p=1, q=2))


def po(a, /, **kw):
    return a, dict(kw)


def keep(**kw):
    get_a = lambda: kw["a"]
    return get_a


def describe(kw):
    return f"{len(kw)} keys: {kw}"


def collect(**kw):
    try:
        return kw["missing"]
    except KeyError as e:
        return f"KeyError {e}"


def fwd(**kw):
    return describe(kw), collect(**kw)


print(po(1, a=2), keep(a="x")(), fwd(n=1, s="s"), collect())


def extended(**kw):
    # (a copy to change, also of a call without extra keywords)
    d = dict(kw)
    d["extra"] = 1
    return d


print(extended(), extended(a=2))
