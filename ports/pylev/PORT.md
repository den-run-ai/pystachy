# pylev 1.4.0

Compute Levenshtein edit distances in five pure-Python variants, including memoized recursion, Wagner–Fischer tables, two-row iteration and adjacent-transposition Damerau distance.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/pylev/) · [License](LICENSE)

```python
from pylev import levenshtein, damerau_levenshtein

print(levenshtein("flaw", "lawn"))
print(damerau_levenshtein("ab", "ba"))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- All five functions and upstream aliases, including `levenshtein` and the historical `levenschtein` spelling.
- The tested sequence inputs are strings, lists of strings and lists of integers. Use comparable item types.
- Annotate an explicitly supplied empty recursion memo as `dict[str, int]`.

<a id="deviations-it-hits"></a>

## Compatibility

- String distances count UTF-8 bytes: `levenshtein("café", "cafe")` is 2, where CPython’s character distance is 1. ASCII strings and word/integer sequences agree.
- Recursive variants are limited by the native stack. Use the iterative variant for long inputs.
- List comparisons involving a shared NaN can differ from CPython’s object-identity shortcut.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_pylev_strings.py
./tests/run.sh ./pystachy "jit aot" tests/port_pylev_strings.py tests/port_pylev_sequences.py tests/port_pylev_imports.py
```

The tests cover upstream pairs, aliases/import forms, empty inputs, transpositions, explicit recursion arguments and list sequences.

Cases: [port_pylev_strings.py](../../tests/port_pylev_strings.py), [port_pylev_sequences.py](../../tests/port_pylev_sequences.py), [port_pylev_imports.py](../../tests/port_pylev_imports.py).

<a id="speed"></a>

## Performance snapshot

A recorded workload of long ASCII-string distances was about **11× faster** than CPython 3.13.16 on upstream. Native libraries such as RapidFuzz and Levenshtein were not compared.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from pylev 1.4.0; license: BSD-3-Clause.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="pylev-140-ported-to-pystachy"></a>
