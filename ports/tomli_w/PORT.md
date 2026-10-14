# tomli-w 1.2.0

Serialize statically typed dictionaries as TOML text with `tomli_w.dumps()`.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/tomli-w/) · [License](LICENSE)

```python
from tomli_w import dumps

print(dumps({"project": {"name": "demo", "version": "1.0"}}))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- Homogeneous containers such as `dict[str, str]`, nested tables, integer arrays and arrays of typed tables. Keys are strings.
- Strings, integers, floats and booleans, escaping, multiline strings and indentation. Each container has one statically determined value/item type.
- Binary `dump()`, mixed-type containers, date/time objects, Decimal values and the upstream identity-based inline-table cache are outside this port’s coverage. Write `dumps()` output to a text file.

<a id="deviations-it-hits"></a>

## Compatibility

- Inline-table line limits count UTF-8 bytes, so long non-ASCII tables may use `[[table]]` layout sooner than CPython. Both layouts parse to the same document.
- Checked 64-bit integers fit TOML’s integer range.
- The cache removal can make small inline-table workloads slower. Many escaped characters in one long string also caused a historical concatenation regression; see the benchmark snapshot.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_tomli_w_values.py
./tests/run.sh ./pystachy "jit aot" tests/port_tomli_w_values.py tests/port_tomli_w_tables.py tests/port_tomli_w_ini2toml.py
```

The differential tests cover scalar escapes, numeric edges, nested/inline tables and an INI-to-TOML example using the iniconfig port.

Cases: [port_tomli_w_values.py](../../tests/port_tomli_w_values.py), [port_tomli_w_tables.py](../../tests/port_tomli_w_tables.py), [port_tomli_w_ini2toml.py](../../tests/port_tomli_w_ini2toml.py).

<a id="speed"></a>

## Performance snapshot

A recorded AOT large-table serialization workload was about **1.5× faster** than CPython 3.13.16 on upstream. Small inline tables and long escape-heavy strings showed regressions in the same measurement record.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from tomli-w 1.2.0; license: MIT.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="tomli-w-120-ported-to-pystachy"></a>
