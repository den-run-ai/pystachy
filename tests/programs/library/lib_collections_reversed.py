# lib/collections: reversed() of a deque and of the mappings, whose __reversed__ steps through
# their items (or keys) from the last.
from collections import Counter, OrderedDict, defaultdict, deque

q = deque([1, 2, 3])
q.appendleft(0)
q.append(4)
print(list(reversed(q)), q, list(reversed(deque[int]())))
q.rotate(2)
print(list(reversed(q)), q, [x * 2 for x in reversed(q)], sum(reversed(q)))
q.popleft()
q.pop()
for x in reversed(q):
    print(x)
w = deque("abc", maxlen=2)
print("".join(reversed(w)), sorted(reversed(w)))
od = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
od.move_to_end("a")
print(list(reversed(od)), [k + "!" for k in reversed(od)], "".join(reversed(od)))
print(list(reversed(od.keys())), list(reversed(od.items())), list(reversed(od.values())))
c = Counter("hello")
print(list(reversed(c)), max(reversed(c)))
d: defaultdict[str, int] = defaultdict(int, {"x": 1, "y": 2})
d["z"]
print(list(reversed(d)))
e: OrderedDict[str, int] = OrderedDict()
print(list(reversed(e)))
