# examples/route: route() of a generated trace in-process, through fnmatch and two caches: the
# events per rule and both caches' statistics, as CPython prints them. Unique names (the second
# trace) push the 4,096 names route() keeps through its cache
import genevents
import route
from fnmatch import _compile_pattern

with open("examples/route/rules.txt") as f:
    route.load(f.readlines())
print(len(route.PATTERNS), route.PATTERNS[:3], route.DESTINATIONS[:3])
counts = [0] * (len(route.PATTERNS) + 1)
for i in range(20000):
    counts[route.route(genevents.event(i, False))] += 1
print(counts)
print(route.route.cache_info())
print(_compile_pattern.cache_info())
for i in range(6000):
    counts[route.route(genevents.event(i, True))] += 1
print(counts)
print(route.route.cache_info())
print(route.route.__wrapped__("auth.login.failed"), route.route("gc.sweep.completed"), route.route("nothing"))
