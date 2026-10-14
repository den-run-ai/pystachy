# ordered-set 4.1.0

Deduplicate strings while preserving insertion order, with integer positions and dictionary-backed membership lookups.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/ordered-set/) · [License](LICENSE)

```python
from ordered_set import OrderedSet

items = OrderedSet(["red", "blue", "red"])
print(list(items), items.index("blue"))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `OrderedSet` of strings: add/update, integer indexing, membership, iteration, copies, discard, pop and clear.
- Set algebra is exposed through methods. `union()`, `intersection()`, `difference()` and `difference_update()` each take one `list[str]`; pass `list(other)` for another ordered set.
- Equality compares ordered sets in order. Generic items, slices/fancy indexing, pickling and the upstream ABC-supplied methods are outside this port’s API.

<a id="deviations-it-hits"></a>

## Compatibility

- The port preserves upstream 4.1.0’s bug: `pop(i)` before the last position leaves later entries’ stored indices stale. Prefer `discard(value)` when removing an interior item.
- Whole non-ASCII string items hash and compare correctly. Constructing items with `list(text)` splits UTF-8 bytes, so it is not a Unicode-character set.
- Some upstream algebra edge cases with duplicate input lists are retained; see the reference and edge tests.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_ordered_set_api.py
./tests/run.sh ./pystachy "jit aot" tests/port_ordered_set_api.py tests/port_ordered_set_edges.py
```

The differential tests cover ordering, API forms, algebra, Unicode string items, mutation, duplicates and the preserved upstream pop bug.

Cases: [port_ordered_set_api.py](../../tests/port_ordered_set_api.py), [port_ordered_set_edges.py](../../tests/port_ordered_set_edges.py).

<a id="speed"></a>

## Performance snapshot

A recorded token-deduplication/index workload was **5.3× faster** than CPython 3.13.16 on upstream and **4.1× faster** than CPython on the same adapted code.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from ordered-set 4.1.0; license: MIT.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="ordered-set-410-ported-to-pystachy"></a>
