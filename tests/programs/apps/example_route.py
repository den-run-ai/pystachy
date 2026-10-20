# examples/route: the router in-process. route() through the rules' compiled patterns and its
# lru_cache, route_fnmatch() through fnmatch and its cache of compiled patterns, then run() over a
# trace file in each mode: the events per rule and the caches' statistics, as CPython prints
# them. Unique names (the second trace) are all misses. The workload is small enough for the
# gc-stress step, which collects at every allocation: bench.py routes a million events, and pushes
# route() past the 4,096 names its cache keeps; tests/programs/library/lib_functools.py covers the evictions
import os
import tempfile
import genevents
import route
from fnmatch import _compile_pattern

with open("examples/route/rules.txt") as f:
    route.load(f.readlines())
print(len(route.PATTERNS), len(route.MATCHERS), route.PATTERNS[:3], route.DESTINATIONS[:3])
counts = [0] * (len(route.PATTERNS) + 1)
again = [0] * (len(route.PATTERNS) + 1)
for i in range(3000):
    name = genevents.event(i, False)
    counts[route.route(name)] += 1
    again[route.route_fnmatch(name)] += 1
print(counts, counts == again)
print(route.route.cache_info())
print(_compile_pattern.cache_info())
for i in range(500):
    counts[route.route(genevents.event(i, True))] += 1
print(counts)
print(route.route.cache_info())
print(route.route.__wrapped__("auth.login.failed"), route.route("gc.sweep.completed"), route.route("nothing"), route.route_fnmatch("db.query.slowest"))

# a trace file: names that repeat, new ones, and a last line without a tab or a newline (its
# name is the whole line)
d = tempfile.mkdtemp()
p = d + "/events.tsv"
with open(p, "w") as f:
    for i in range(600):
        f.write(f"{genevents.event(i, i % 3 == 0)}\t{1760000000 + i}\t{i % 977}\n")
    f.write("http.request.404")
modes: list[list[str]] = [[], ["--names"], ["--no-cache"], ["--fnmatch", "--names"]]
for opts in modes:
    print(opts)
    route.run("examples/route/rules.txt", p, opts)
os.remove(p)
os.rmdir(d)
