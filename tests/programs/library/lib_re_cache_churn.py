# A frequently used pattern survives one-use patterns, including equal but freshly built keys.
import re

re.purge()
source = "(?P<word>[a-z]+)"
hot = re.compile(source)
folded = re.compile(source, re.I)
recompiled = 0
for i in range(1025):
    equal_source = ("." + source)[1:]
    if re.compile(equal_source) is not hot:
        recompiled += 1
    if re.compile(equal_source, re.I) is not folded:
        recompiled += 1
    re.compile("cold-pattern-" + str(i))
print("hot recompiles", recompiled)
print("distinct flags", hot is not folded)
print("result", folded.findall("ABC def"))
re.purge()
print("purged", re.compile(source) is not hot)
