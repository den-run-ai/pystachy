# Adapted from CPython 3.13.16 Lib/test/test_extcall.py (a doctest: its "Argument list examples",
# "Here we add keyword arguments" and the g() calls of its invalid-argument section), with
# test.support.sortdict from Lib/test/support/__init__.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each doctest example is a statement here whose comment is the output the doctest expects;
# sortdict() returns "{}" for an empty **kwargs before calling items(), which is rejected
# there (existing issue #240).
# EXCLUDED upstream examples:
# - the TypeErrors of calls whose arguments do not fit (multiple values for a keyword, missing,
#   unexpected and too many arguments): compile-time errors here, with CPython's messages, in
#   tests/errors/upstream/upstream_extcall_*.py
# - UserList and UserDict arguments (collections), `**d1` and `**d` of dict variables, `**` of a
#   dict with an int key ("keywords must be strings"), `*` and `**` of a function, a list or
#   None, and dir(): only a tuple's items (or a list or tuple display's) can be `*` arguments,
#   and only a function's own **kwargs (or a dict display with str keys) a `**` argument
# - `*` of objects that iterate (Nothing, BrokenIterable1/2, BrokenSequence) or of generator
#   expressions (`g(*(broken() for i in range(1)))`, issue #4806), and generators
# - saboteur(): a **kwargs changed by the function (rejected; copy it with dict())
# - MultiDict (a Mapping subclass), MyDict (a dict subclass), Name (a str subclass): inheritance
# - f2(1, *(2,3), **d) with 512 keys, `Foo.method(*(x, 1, 2))` (a method called through its
#   class), id(1, *{}) and id(1, **{'foo': 1})


def sortdict(dict):
    "Like repr(dict), but in sorted order."
    if not dict:
        return "{}"  # (Pystachy: issue #240)
    items = sorted(dict.items())
    reprpairs = ["%r: %r" % pair for pair in items]
    withcommas = ", ".join(reprpairs)
    return "{%s}" % withcommas


def f(*a, **k):
    print(a, sortdict(k))


def g(x, *y, **z):
    print(x, y, sortdict(z))


# Argument list examples

f()                                 # () {}
f(1)                                # (1,) {}
f(1, 2)                             # (1, 2) {}
f(1, 2, 3)                          # (1, 2, 3) {}
f(1, 2, 3, *(4, 5))                 # (1, 2, 3, 4, 5) {}
f(1, 2, 3, *[4, 5])                 # (1, 2, 3, 4, 5) {}
f(*[1, 2, 3], 4, 5)                 # (1, 2, 3, 4, 5) {}
f(1, 2, 3, *[4, 5], *[6, 7])        # (1, 2, 3, 4, 5, 6, 7) {}
f(1, *[2, 3], 4, *[5, 6], 7)        # (1, 2, 3, 4, 5, 6, 7) {}

# Here we add keyword arguments

f(1, 2, 3, **{'a':4, 'b':5})                        # (1, 2, 3) {'a': 4, 'b': 5}
f(1, 2, 3, *[4, 5], **{'a':6, 'b':7})               # (1, 2, 3, 4, 5) {'a': 6, 'b': 7}
f(1, 2, 3, x=4, y=5, *(6, 7), **{'a':8, 'b': 9})    # (1, 2, 3, 6, 7) {'a': 8, 'b': 9, 'x': 4, 'y': 5}
f(1, 2, 3, *[4, 5], **{'c': 8}, **{'a':6, 'b':7})   # (1, 2, 3, 4, 5) {'a': 6, 'b': 7, 'c': 8}
f(1, 2, 3, *(4, 5), x=6, y=7, **{'a':8, 'b': 9})    # (1, 2, 3, 4, 5) {'a': 8, 'b': 9, 'x': 6, 'y': 7}

# The calls of g that fit its parameters

g(1)                                # 1 () {}
g(1, 2)                             # 1 (2,) {}
g(1, 2, 3)                          # 1 (2, 3) {}
g(1, 2, 3, *(4, 5))                 # 1 (2, 3, 4, 5) {}
