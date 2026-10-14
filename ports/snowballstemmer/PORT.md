# snowballstemmer 3.1.1

Stem English search-index words with Snowball’s Porter2 `EnglishStemmer` or the original `PorterStemmer`.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/snowballstemmer/) · [License](LICENSE)

```python
from snowballstemmer import EnglishStemmer

print(EnglishStemmer().stemWords(["connection", "connected", "connecting"]))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- The two English classes, `stemWord()`, `stemWords(list[str])` and their tested cursor operations.
- Both classes inherit the shared `BaseStemmer`, as upstream does; inherited `stemWord()` calls each subclass's `_stem()`.
- `algorithms()` reports `english` and `porter`. Construct the classes directly; the pure-Python `stemmer(lang)` factory is omitted.
- The other 34 languages, `Among` method callbacks and PyStemmer’s C extension are outside this port.

<a id="deviations-it-hits"></a>

## Compatibility

ASCII English inputs follow upstream. Non-ASCII words can stem differently because the cursor counts UTF-8 bytes: `boñing` becomes `boñ` rather than CPython’s `boñe`. This port is not a general Unicode-language stemmer.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_snowballstemmer_stem.py
./tests/run.sh ./pystachy "jit aot" tests/port_snowballstemmer_stem.py
```

The differential program checks 384 selected words against recorded Porter2/Porter stems, suffix-rule edges, cursor APIs, long words and pseudo-random ASCII inputs.

Cases: [port_snowballstemmer_stem.py](../../tests/port_snowballstemmer_stem.py).

<a id="speed"></a>

## Performance snapshot

The recorded AOT workload of 400,000 stems was about **13× faster** than CPython 3.13 on upstream’s pure-Python classes. PyStemmer was not compared.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from snowballstemmer 3.1.1; license: BSD-3-Clause.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="snowballstemmer-311-ported-to-pystachy"></a>
<a id="the-flattening"></a>

The [inheritance record](PORT_REFERENCE.md#the-flattening) describes the restored upstream hierarchy.
