# "format" % mapping with conversions that name keys, %(key)s: dicts, OrderedDict and
# defaultdict (whose lookup makes the missing value), a key CPython reads to its closing
# parenthesis, a mapping no conversion uses, and KeyError for a missing key.
from collections import OrderedDict, defaultdict

d = {"name": "x", "other": "why"}
print("%(name)s has %(other)s" % d)
print("%(name)5s|%(name)-5s|%(name)r|%%(name)s" % d)
n = {"a": 1, "b": -22}
print("%(a)d-%(b)s-%(a)05d-%(b)+d-%(a)x-%(b)i" % n)
f = {"pi": 3.14159, "e": 2.71828}
print("%(pi).2f %(e)8.3f %(pi)g %(e)e" % f)
print("plain" % d, "100%%" % d)
m = {"a b": "spaced", "a(b)": "nested", "": "empty"}
print("%(a b)s %(a(b))s %()s" % m)
print("%(name)s-%(name)s" % {"name": "y"})
FMT = "%(k)s=%(v)s"
print(FMT % {"k": "key", "v": "value"})
od = OrderedDict([("x", 1), ("y", 2)])
print("%(y)d %(x)d" % od)
dd: defaultdict[str, int] = defaultdict(int)
dd["seen"] = 7
print("%(seen)d %(unseen)d" % dd, len(dd))
try:
    print("%(name)s %(missing)s" % d)
except KeyError as e:
    print("KeyError", e)


def fmt(values: dict[str, str]) -> str:
    return "<%(tag)s class=%(cls)r>" % values


print(fmt({"tag": "div", "cls": "a"}))
mixed = {"s": "text", "i": 3}
print("%(s)s %(i)s %(i)r" % mixed)
