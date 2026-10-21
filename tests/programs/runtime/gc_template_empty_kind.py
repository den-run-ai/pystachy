# An empty set or dict that a template returns gets the type its caller expects, here of strs, after
# it was made (typed_empty): the strs added to it must stay alive through collections (run with
# PYSTACHY_GC_STRESS_PROGRAM=1, as the gc-stress step does). Int keys and elements, whose tables
# the collector does not scan (#210), keep their values too.


def make_set(n):
    s = set()
    return s


def make_dict(n):
    d = {}
    return d


names: set[str] = make_set(1)
table: dict[str, int] = make_dict(2)
counts: set[int] = make_set(3)
for i in range(300):
    names.add(str(i) * 40)
    table[str(i) * 30] = i
    counts.add(i * 1000003)
    if i % 75 == 0 or i < 5:
        print(i, len(names), min(names)[:12], len(table), min(table)[:9], len(counts))
print(len(names), sum(len(x) for x in names), sum(len(k) + v for k, v in table.items()), sum(counts))
print(sorted(names)[:2], sorted(table)[-1][:6], sorted(counts)[-3:])
