# wcwidth 0.9.2

Measure terminal-cell widths for Unicode characters and text, including CJK, combining marks, emoji clusters and ambiguous-width characters.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/wcwidth/) · [License](LICENSE)

```python
from wcwidth import wcwidth, wcswidth

print(wcwidth("中"), wcswidth("中文"))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `wcwidth()` and `wcswidth()`, ambiguous width 1/2, character-count `n=` and the included Unicode width/grapheme tables.
- The Unicode-version parameter follows upstream’s accepted/ignored behavior for this release.
- Per-terminal overrides, `wcstwidth()`, terminal discovery, wrapping/alignment/escape-sequence APIs and the C extension are outside the tested port coverage.
- `wcwidth` retains upstream's 1,024-entry LRU cache, including `cache_info`, `cache_clear`
  and `__wrapped__`. Default and keyword calls keep their upstream cache-key forms.
  The private `_wcmatch_version` helper also retains its eight-entry cache; the legacy
  variable-length-tuple parser `_wcversion_value` remains outside the compiled API.

<a id="deviations-it-hits"></a>

## Compatibility

- `wcswidth()` splits well-formed UTF-8 sequences before measuring characters, so literals and `n=` match the tested CPython widths.
- A caller’s own `len()`, slicing or iteration still counts bytes: `wcswidth("中文", len("中"))` measures both characters in Pystachy, while CPython measures one.
- Raw bytes produced by `chr()` or incomplete text slices have the documented byte-decoding behavior; boolean width/count arguments are outside the typed API.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_wcwidth_core.py
./tests/run.sh ./pystachy "jit aot" tests/port_wcwidth_core.py tests/port_wcwidth_edges.py
```

The tests adapt upstream core/emoji/ambiguous-width cases and add table boundaries, controls, UTF-8/raw-byte edges and character-count limits.

Cases: [port_wcwidth_core.py](../../tests/port_wcwidth_core.py), [port_wcwidth_edges.py](../../tests/port_wcwidth_edges.py),
[port_wcwidth_cache.py](../../tests/port_wcwidth_cache.py). The cache case checks warm hits,
default/keyword keys, clearing, error misses and eviction while retaining Unicode width results.

<a id="speed"></a>

## Performance snapshot

A recorded AOT mixed-Unicode-width workload was about **10× faster** than CPython 3.13.16 on upstream’s pure-Python implementation, including its cache. The available C extension was not compared.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from wcwidth 0.9.2; license: MIT with Markus Kuhn notice.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="wcwidth-092-ported-to-pystachy"></a>
