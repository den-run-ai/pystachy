# Cache hits, purge and eviction, including replacement templates whose group indices depend
# on flags. The cache keys must keep the original pattern, flags and replacement apart.
import re

re.purge()
source = "(?P<word>[a-z]+)"
first = re.compile(source)
equal_source = ("." + source)[1:]
print("equal hit", first is re.compile(equal_source))
print("flags", first is re.compile(source, re.I), re.compile(first) is first)
re.purge()
print("purged", first is re.compile(source))

re.purge()
oldest = re.compile("cache-oldest")
for i in range(512):
    re.compile("cache-entry-" + str(i))
print("evicted", oldest is re.compile("cache-oldest"))

source = "#(x)\n(?P<letter>a)"
plain = re.compile(source).match("#x\na")
verbose = re.compile(source, re.X).match("a")
assert plain is not None and verbose is not None
for _ in range(3):
    print("flagged templates", plain.expand(r"<\g<letter>>"), verbose.expand(r"<\g<letter>>"))

nul = re.compile("(?P<part>a\x00b)").match("a\x00b")
assert nul is not None
print("nul", repr(nul.expand(r"<\g<part>>")))

total = 0
for i in range(520):
    total += len(verbose.expand(str(i) + r"\g<letter>"))
print("template churn", total, verbose.expand(r"<\g<letter>>"))
re.purge()
print("template purge", verbose.expand(r"<\g<letter>>"))
for _ in range(2):
    try:
        verbose.expand(r"\2")
    except re.error as error:
        print("uncached error", error)
