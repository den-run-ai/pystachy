# Fixed-universe ID filtering: independent set oracle and real search consumer.
from idset import IdSet, from_ids
from query_bench import inputs, query_bitmap, query_sets, set_count
from search import SearchIndex, sample_documents


def check(capacity: int) -> None:
    left = IdSet(capacity)
    right = IdSet(capacity)
    a: set[int] = set()
    b: set[int] = set()
    # Fill complete words as well as padding, then exercise duplicate/missing mutations.
    for value in range(capacity):
        left.add(value)
        a.add(value)
        if value % 3 != 0:
            right.add(value)
            right.add(value)
            b.add(value)
    for value in range(0, capacity, 5):
        left.discard(value)
        left.discard(value)
        a.discard(value)
    for value in range(capacity):
        assert left.contains(value) == (value in a)
        assert right.contains(value) == (value in b)
    assert left.ids() == sorted(a)
    assert right.ids() == sorted(b)
    assert left.count() == len(a)
    assert right.count() == len(b)
    assert left.intersection(right).ids() == sorted(a & b)
    assert left.union(right).ids() == sorted(a | b)
    assert left.difference(right).ids() == sorted(a - b)
    assert right.difference(left).ids() == sorted(b - a)
    assert left.intersection_count(right) == len(a & b)
    assert right.intersection_count(left) == len(a & b)
    assert left.intersection_count(left) == len(a)
    assert left.difference(left).count() == 0
    assert left.union(left).ids() == left.ids()
    # Result masks and exported lists own independent storage.
    copy = left.union(left)
    exported = right.ids()
    if capacity:
        copy.add(0)
        right.discard(capacity - 1)
        assert not left.contains(0)
        assert exported == sorted(b)
    assert left.capacity() == capacity
    assert left.storage_words() == capacity // 63 + (1 if capacity % 63 else 0)
    print(capacity, left.count(), len(b), left.intersection(right).ids()[:8])


for capacity in [0, 1, 2, 62, 63, 64, 125, 126, 127, 1025]:
    check(capacity)

# Exactly 63 low bits set: int64 maximum, with no signed shifts or padding IDs.
full = from_ids(64, list(range(63)))
assert full.count() == 63 and full.ids() == list(range(63))
full.add(63)
assert full.count() == 64
assert full.ids()[-2:] == [62, 63]
assert from_ids(127, [0, 62, 63, 64, 125, 126, 63]).ids() == [0, 62, 63, 64, 125, 126]

# Out-of-universe membership, insertions and deletions all reject explicitly.
for capacity in [0, 1, 63, 64]:
    mask = IdSet(capacity)
    for value in [-9223372036854775807 - 1, -1, capacity, 9223372036854775807]:
        errors = 0
        try:
            mask.add(value)
        except ValueError:
            errors += 1
        try:
            mask.discard(value)
        except ValueError:
            errors += 1
        try:
            mask.contains(value)
        except ValueError:
            errors += 1
        assert errors == 3 and mask.count() == 0
print("invalid IDs rejected")
for capacity in [-9223372036854775807 - 1, -1]:
    try:
        IdSet(capacity)
    except ValueError as error:
        print(str(error))

# Same word count is not enough: capacity is part of the universe contract.
for capacity in [0, 62, 63, 64]:
    left = IdSet(capacity)
    right = IdSet(capacity + 1)
    errors = 0
    try:
        left.intersection_count(right)
    except ValueError:
        errors += 1
    try:
        left.intersection(right)
    except ValueError:
        errors += 1
    try:
        left.union(right)
    except ValueError:
        errors += 1
    try:
        left.difference(right)
    except ValueError:
        errors += 1
    assert errors == 4
print("different universes rejected")

# A changing sparse workload with a deterministic independent membership oracle.
mask = IdSet(257)
oracle: set[int] = set()
state = 7
for step in range(400):
    state = (state * 37 + 11) % 257
    if step % 3:
        mask.add(state)
        oracle.add(state)
    else:
        mask.discard(state)
        oracle.discard(state)
    assert mask.count() == len(oracle)
    assert mask.ids() == sorted(oracle)
print("changing IDs", mask.count(), mask.ids()[:10])

documents = sample_documents()
index = SearchIndex(documents)
for language in ["en", "fr", "missing"]:
    for tag in ["python", "compiler", "numeric", "graph", "search", "missing"]:
        expected: list[str] = []
        for title, lang, tags, blocked in documents:
            if language == lang and tag in tags.split() and not blocked:
                expected.append(title)
        assert index.matches(tag, language) == expected
        assert index.count(tag, language) == len(expected)
print(index.matches("python", "en"))
empty = SearchIndex([])
assert empty.count("python", "en") == 0
assert empty.matches("python", "en") == []
print("search oracle passed")

# Exercise the benchmark's changing-query contract with an independent set oracle.
for capacity, stride in [(0, 2), (1, 1), (63, 2), (127, 64), (257, 7)]:
    values, selected = inputs(capacity, stride)
    assert len(values) == len(range(0, capacity, stride))
    assert len(set(values)) == len(values)
    assert len(set(selected)) == len(selected)
    for value in values + selected:
        assert 0 <= value < capacity
    for repeats in [0, 1, 2, 10, 200]:
        a = set(values)
        b = set(selected)
        expected_count = 0
        for step in range(repeats):
            if values:
                value = values[step % len(values)]
                if (step // len(values)) % 2:
                    a.add(value)
                else:
                    a.discard(value)
            assert set_count(a, b) == len(a & b)
            expected_count += len(a & b)
        mask = from_ids(capacity, values)
        assert query_bitmap(mask, from_ids(capacity, selected), values, repeats) == expected_count
        assert mask.ids() == sorted(a)
        for materialize in [False, True]:
            actual = set(values)
            assert query_sets(actual, set(selected), values, repeats, materialize) == expected_count
            assert sorted(actual) == sorted(a)
print("benchmark controls agree")
