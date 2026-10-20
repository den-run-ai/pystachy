# ordered-set's OrderedSet: the cases of its own test suite (test/test_ordered_set.py of
# ordered-set 4.1.0) and the examples of its docstrings, run as a program with str items
from ordered_set import OrderedSet

# test_order (reversed() is not ported: see PORT.md)
set1 = OrderedSet(list("abracadabra"))
print("order:", len(set1), set1 == OrderedSet(["a", "b", "r", "c", "d"]), list(set1))

# test_binary_operations: &, | and - as the methods they stand for, given lists
set2 = OrderedSet(list("simsalabim"))
print("binary:", set1 != set2, set1.__and__(list(set2)), set1.intersection(list(set2)) == OrderedSet(["a", "b"]))
print("binary:", set1.union(list(set2)) == OrderedSet(list("abrcdsiml")), set1.difference(list(set2)))

# test_indexing: copies and index() of one key
print("indexing:", set1.copy() == set1, set1 is set1, set1.copy() is not set1, set1.index("b"))
try:
    set1.index("br")
except KeyError as e:
    print("KeyError", e)

# test_pandas_compat
print("pandas:", set1.get_loc("b"), set1.get_indexer("r"))

# test_remove, with discard() (MutableSet's remove() is not ported)
set1 = OrderedSet(list("abracadabra"))
set1.discard("a")
set1.discard("b")
print("remove:", set1 == OrderedSet(list("rcd")), set1[0], set1[1], set1[2])
print("remove:", set1.index("r"), set1.index("c"), set1.index("d"), "a" not in set1, "b" not in set1, "r" in set1)
set1.discard("a")
set1.discard("a")
print("remove:", set1, "z" in set1)

# test_clear
set1 = OrderedSet(list("abracadabra"))
set1.clear()
print("clear:", len(set1), set1 == OrderedSet(), set1)

# test_update
set1 = OrderedSet(list("abcd"))
result = set1.update(list("efgh"))
print("update:", result, len(set1), "".join(set1))
set2 = OrderedSet(list("abcd"))
result = set2.update(list("cdef"))
print("update:", result, len(set2), "".join(set2))

# test_pop
set1 = OrderedSet(list("ab"))
print("pop:", set1.pop(), set1.pop())
try:
    set1.pop()
except KeyError as e:
    print("KeyError", e)

# test_empty_repr, test_ordered_equality, test_ordered_inequality (of OrderedSets)
print("repr:", repr(OrderedSet()), OrderedSet(["1", "2"]) == OrderedSet(["1", "2"]), OrderedSet(["1", "2"]) != OrderedSet(["2", "1"]))


# test_operator_consistency_*: _operator_consistency_testdata with a linear congruential
# generator for random.Random(0), and check_results_
def check(name: str, results: list[OrderedSet]) -> None:
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            if results[i] != results[j] or results[i] is results[j]:
                raise AssertionError("%s: %r and %r" % (name, results[i], results[j]))


pairs: list[tuple[OrderedSet, OrderedSet]] = [
    (OrderedSet(["5", "3", "1", "4"]), OrderedSet(["1", "4"])),
    (OrderedSet([]), OrderedSet(["3", "1", "2"])),
    (OrderedSet(["3", "1", "2"]), OrderedSet([])),
    (OrderedSet([]), OrderedSet([])),
]
x = 0
for _ in range(10):
    items1: list[str] = []
    items2: list[str] = []
    for _ in range(20):
        x = (x * 1103515245 + 12345) % 2147483648
        items1.append(str(x % 21))
        x = (x * 1103515245 + 12345) % 2147483648
        items2.append(str(x % 21))
    pairs.append((OrderedSet(items1), OrderedSet(items2)))
    pairs.append((OrderedSet(items2), OrderedSet(items1)))
# test_bitwise_and_consistency
pairs.append((OrderedSet("12 13 1 8 16 15 9 11 18 6 4 3 19 17".split()), OrderedSet("19 4 9 3 2 10 15 17 11 13 20 6 14 16 8".split())))
for data1, data2 in pairs:
    other = list(data2)
    isect = data1.copy()
    isect.intersection_update(other)
    check("isect", [isect, data1.__and__(other), data1.intersection(other)])
    diff = data1.copy()
    diff.difference_update(other)
    check("difference", [diff, data1.difference(other)])
    xor = data1.copy()
    xor.symmetric_difference_update(other)
    check("xor", [xor, data1.symmetric_difference(other)])
    union = data1.copy()
    union.update(other)
    check("union", [union, data1.union(other)])
    subset = all(item in data2 for item in data1)
    superset = all(item in data1 for item in data2)
    if data1.issubset(other) != subset or data1.issuperset(other) != superset:
        raise AssertionError("subset/superset of %r and %r" % (data1, data2))
    print(len(data1), len(data2), subset, superset, len(isect) == 0, "|", " ".join(isect), "|", " ".join(diff), "|", " ".join(xor), "|", " ".join(union))

# the examples of the docstrings
print(OrderedSet(["1", "1", "2", "3", "2"]), len(OrderedSet([])), len(OrderedSet(["1", "2"])), OrderedSet(["1", "2", "3"])[1])
this = OrderedSet(["1", "2", "3"])
other_set = this.copy()
print(this == other_set, this is other_set, "1" in OrderedSet(["1", "3", "2"]), "5" in OrderedSet(["1", "3", "2"]))
oset = OrderedSet()
print(oset.append("3"), oset)
oset = OrderedSet(["1", "2", "3"])
print(oset.update(["3", "1", "5", "1", "4"]), oset, oset.index("2"), OrderedSet(["1", "2", "3"]).pop())
oset = OrderedSet(["1", "2", "3"])
oset.discard("2")
print(oset)
oset.discard("2")
print(oset, list(OrderedSet(["1", "2", "3"])), OrderedSet(["1", "3", "2"]) == OrderedSet(["3", "2", "1"]))
oset = OrderedSet(["3", "1", "4", "1", "5"]).union(["1", "3"]).union(["2", "0"])
print(oset, oset.union(["8", "9"]), oset.union(["10"]))
oset = OrderedSet(["0", "1", "2", "3"]).intersection(["1", "2", "3"])
print(oset, oset.intersection(["2", "4", "5"]).intersection(["1", "2", "3", "4"]), oset.intersection(list(oset)))
print(OrderedSet(["1", "2", "3"]).difference(["2"]), OrderedSet(["1", "2", "3"]).difference(["2"]).difference(["3"]), OrderedSet(["1", "2", "3"]).difference([]))
print(OrderedSet(["1", "2", "3"]).issubset(["1", "2"]), OrderedSet(["1", "2", "3"]).issubset(["1", "2", "3", "4"]), OrderedSet(["1", "2", "3"]).issubset(["1", "4", "3", "5"]))
print(OrderedSet(["1", "2"]).issuperset(["1", "2", "3"]), OrderedSet(["1", "2", "3", "4"]).issuperset(["1", "2", "3"]), OrderedSet(["1", "4", "3", "5"]).issuperset(["1", "2", "3"]))
this = OrderedSet(["1", "4", "3", "5", "7"])
other = ["9", "7", "1", "3", "2"]
print(this.symmetric_difference(other))
this = OrderedSet(["1", "2", "3"])
this.difference_update(["2", "4"])
print(this)
this = OrderedSet(["1", "2", "3", "4", "5"])
this.difference_update(["2", "4"], ["1", "4", "6"])
print(this)
this = OrderedSet(["1", "4", "3", "5", "7"])
this.intersection_update(other)
print(this)
this = OrderedSet(["1", "4", "3", "5", "7"])
this.symmetric_difference_update(other)
print(this)

# No arguments must keep both populated and empty sets unchanged.
this = OrderedSet(["b", "a", "b"])
this.difference_update()
print(this)
empty = OrderedSet()
empty.difference_update()
print(empty)
