# Documented deviations of lib/re (Pystachy's port of CPython's re) from CPython 3.13.
import re

# The flags are ints, not re.RegexFlag members; CPython prints re.IGNORECASE re.IGNORECASE|re.MULTILINE
print(re.I, re.I | re.M)

# Pattern.groupindex is a dict; CPython prints mappingproxy({'a': 1})
print(repr(re.compile("(?P<a>x)").groupindex))

# finditer() returns a list of the matches, all found before it returns; CPython's iterator has
# no len(): TypeError: object of type 'callable_iterator' has no len()
print(len(re.finditer("a", "banana")))

# \N{...} needs the Unicode character names, which Pystachy does not have: a pattern error.
# CPython compiles it to the character (here an em dash)
try:
    re.compile(r"\N{EM DASH}")
except re.error as e:
    print("error:", e)

# re.split() of a pattern with a group that does not take part in a match: CPython puts None in
# the list, which a list[str] cannot hold. CPython prints ['a', None, 'b']
try:
    print(re.split("(x)|y", "ayb"))
except NotImplementedError as e:
    print("NotImplementedError:", e)

# re.findall() of a pattern with 2 groups or more returns tuples as long as the group count,
# which have no type in Pystachy: an error when it runs. CPython prints [('a', '1'), ('b', '2')]
print(re.findall(r"(\w)=(\d)", "a=1 b=2"))
