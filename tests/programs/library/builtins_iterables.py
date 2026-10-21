# min/max/sorted/sum/any/all/list of dicts (their keys) and tuples; reverse=; dict.pop
# with a default; sum's start values; [] in a list of lists.
d = {"a": 1, "b": 2}
t = (3, 9, 1)
print(max(d), min(t), sorted(d), sorted(t), list(t), sum(t), sum(d.values()))
print(sorted({3: "x", 1: "y"}, reverse=True), sorted([3, 1, 2], reverse=True), sorted([1, 2], reverse=0))
xs = [5, 2, 8, 1]
xs.sort(reverse=True)
print(xs)
xs.sort()
print(xs)
pairs = [(1, "b"), (0, "a"), (1, "a"), (0, "b")]
print(sorted(pairs, reverse=True))
print(d.pop("b", 0), d.pop("zz", 7), d)
print(sum(x > 0 for x in [3, -1, 4]), sum([1, 2], 0.5), sum([0.5, 1.5], 1), sum([True, True]), sum([0.1, 0.2], 1))
print(sum([1e100, 1.0, -1e100], 1), sum([0.1] * 10, 0), sum([3, 4], int(True)), sum([2**53, 1, 1], 0.0))
prices: list[float] = []
print(sum(prices, 0.0))
rows = [[1, 2], [3]]
print([] in rows, [] not in rows, [3] in rows, {} in [{"a": 1}])
print(any((True, False)), all((True, False)), max("hello"), min(("b", "a")))
counts: dict[str, list[int]] = {"x": []}
counts["x"].append(1)
counts["y"] = []
print(counts)
