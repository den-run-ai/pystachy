# Dictionary hash caches belong to immutable string objects, including writable literals.
# Run with PYSTACHY_GC_STRESS_PROGRAM=1 to collect at every allocation.
literal = "literal-key"
d = {literal: 1, "": 2, "x": 3, "a\x00b": 4}
print("literals", [d[k] for k in [literal, "", "x", "a\x00b"]] * 2)

# Each construction path must start with an empty cache, even after its inputs were hashed.
source = "AbC-123"
inputs = {source: 99}
made = [source + "!", source * 2, source[1:5], source[0], chr(90), str(1234),
        "|".join([source, "tail"]), source.lower(), source.replace("123", "456"),
        f"{source}:7", "  trimmed  ".strip(), "a,b".split(",")[1]]
constructed: dict[str, int] = {}
for i in range(len(made)):
    constructed[made[i]] = i
print("constructed", [constructed[("!" + k)[1:]] for k in made], inputs[source])

long_a = "a" * 4096 + "-key"
equal_a = ("!" + long_a)[1:]
long_b = "b" * 4096 + "-key"
absent = "c" * 4096 + "-key"
d = {long_a: 7, long_b: 11}
total = 0
for i in range(100):
    k = long_a if i % 2 == 0 else long_b
    total += d[k] + d[equal_a] + d.get(absent, -1)
    d[equal_a] = 7
print("long", len(d), total, long_a == equal_a, absent in d)

# Resize repeatedly, remove holes, and reinsert using equal-but-distinct queries.
keys = ["prefix-" + str(i) + "-" + "x" * 80 for i in range(256)]
for i in range(len(keys)):
    d[keys[i]] = i
for i in range(0, len(keys), 2):
    del d[("!" + keys[i])[1:]]
for i in range(0, len(keys), 4):
    d[keys[i]] = 1000 + i
print("resize", len(d), sum([d.get(k, -1) for k in keys]), d[long_a], d[equal_a], d[long_b])
print("delete", d.pop(equal_a), long_a in d)
d[equal_a] = 19
print("reinsert", d[long_a], list(d.keys())[-1] == long_a)

# String tuple components share caches across dictionaries and nested tuple keys.
tuples = {(long_a, 3, long_b): 23}
nested = {((literal, long_a), 5): 29}
total = 0
for i in range(40):
    total += tuples[(equal_a, 3, long_b)] + nested[(("literal-key", equal_a), 5)]
print("tuples", total, tuples.pop((equal_a, 3, long_b)), len(tuples))

# Retain cached keys while temporary string dictionaries churn; reused allocations must
# not carry a previous occupant's cached hash. GC-stress runs collect during this loop.
churn = 0
for r in range(40):
    transient: dict[str, int] = {}
    for i in range(30):
        k = str(r) + ":" + str(i) + "-" + "q" * 32
        transient[k] = i
        churn += transient[("!" + k)[1:]]
    churn += d[long_a] + d[long_b] + nested[((literal, equal_a), 5)]
print("churn", churn, d[equal_a], nested[((literal, long_a), 5)])
