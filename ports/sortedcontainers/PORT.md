# sortedcontainers 2.4.0

Maintain a sorted list of integers with insertion/removal, bisection, ranks, positional access and range queries.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/sortedcontainers/) · [License](LICENSE)

```python
from sortedcontainers import SortedList

values = SortedList([4, 1, 3])
values.add(2)
print(list(values), values.bisect_left(3))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `SortedList` of integers, constructed/updated from `list[int]`; convert other iterables with `list()`.
- Add/remove/discard, integer indexing/deletion, pop, bisect/count/index, copies and tested list arithmetic/comparisons.
- `irange()` and `islice()` return lists. Comparisons are between sorted lists; compare `list(sl)` when comparing with a plain sequence.
- Generic values, `key=`, `SortedKeyList`, `SortedDict`, `SortedSet`, slices, `_check()` and pickling are outside the validated API. Use an explicit import rather than `import *`.

<a id="deviations-it-hits"></a>

## Compatibility

- Iteration uses a snapshot of the values. Mutating the sorted list during a loop differs from upstream’s live sublist iterator.
- Range-query lists can be iterated repeatedly and are false when empty; upstream returns single-use, always-truthy iterators.
- The minimum 64-bit index can raise overflow where upstream raises `IndexError`. Ordering against `None` has a different error message.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_sortedcontainers_api.py
./tests/run.sh ./pystachy "jit aot" tests/port_sortedcontainers_api.py tests/port_sortedcontainers_index.py
```

The tests cover API/error forms, comparisons, duplicates, sublist splitting/merging and positional-index-tree invariants.

Cases: [port_sortedcontainers_api.py](../../tests/port_sortedcontainers_api.py), [port_sortedcontainers_index.py](../../tests/port_sortedcontainers_index.py).

<a id="speed"></a>

## Performance snapshot

A recorded AOT sliding-window median/rank workload was **9.0× faster** by wall time than CPython 3.13.16 on upstream. Native sorted-container libraries were not compared.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from sortedcontainers 2.4.0; license: Apache-2.0.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="sortedcontainers-240-ported-to-pystachy"></a>
