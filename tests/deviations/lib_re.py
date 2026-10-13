# Documented deviations of lib/re (Pystachy's port of CPython's re) from CPython 3.13.
import re

# A position is an index into the str, which holds UTF-8 in Pystachy, as slicing and find() count
# it: past ASCII, a match's spans count bytes. CPython prints 3 4 (3, 4) and 1 4.
m = re.search("é", "café")
if m is not None:
    print(m.start(), m.end(), m.span(), "café"[m.start():m.end()] == m.group())
m = re.search(r"\w+", "€uro")
if m is not None:
    print(m.start(), m.end())

# A pos or endpos inside a character's bytes: the match starts after that character, or ends
# before it, and m.pos and m.endpos are the bounds as given (CPython's count code points)
print(re.compile(".").match("é", 0, 1))
m = re.compile(".").search("aéb", 2)
if m is not None:
    print(m.span(), m.group(), m.pos, m.endpos)
m = re.compile(".+").search("aéb", 0, 2)
if m is not None:
    print(m.span(), m.group(), m.pos, m.endpos)
print([x.group() for x in re.compile(".").finditer("éé", 1, 3)], re.compile(".").fullmatch("éa", 1, 3))

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

# An inline flag that is no flag: the message is "unknown flag" for a character an identifier may
# begin with, where CPython's is for a letter (str.isalpha()), which U+2160 ROMAN NUMERAL ONE is
# not. CPython prints "missing -, : or ) 3" and "missing flag 3"
for p in ["(?i\u2160)", "(?-\u2160:x)"]:
    try:
        re.compile(p)
    except re.error as e:
        print("error:", e.msg, e.pos)

# re.split() of a pattern with a group that does not take part in a match: CPython puts None in
# the list, which a list[str] cannot hold. CPython prints ['a', None, 'b']
try:
    print(re.split("(x)|y", "ayb"))
except NotImplementedError as e:
    print("NotImplementedError:", e)

# re.findall() of a pattern with 2 groups or more returns tuples as long as the group count,
# which have no type in Pystachy: an error when it runs. CPython prints [('a', '1'), ('b', '2')]
print(re.findall(r"(\w)=(\d)", "a=1 b=2"))
