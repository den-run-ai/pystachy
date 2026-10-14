# sqids 0.5.2

Encode lists of nonnegative integers as short URL-safe IDs and decode them, with custom alphabets, minimum lengths and blocked words.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/sqids/) · [License](LICENSE)

```python
from sqids import Sqids

sqids = Sqids()
identifier = sqids.encode([1, 2, 3])
print(identifier, sqids.decode(identifier))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `Sqids(alphabet, min_length, blocklist)`, `encode(list[int])` and `decode(str)`, with upstream defaults and error messages.
- ASCII alphabets and `list[str]` custom blocklists; minimum length is an integer from 0 to 255.
- Encoded integers range from 0 to `sys.maxsize`; booleans, tuple/range input and non-list blocklists are outside the annotated API.

<a id="deviations-it-hits"></a>

## Compatibility

- Encoded values round-trip within 64 bits. Decoding arbitrary oversized/noncanonical IDs can overflow, even if upstream returns a small value after leading zero digits.
- Non-ASCII alphabet characters are rejected. Blocklist case normalization is ASCII-only, so Unicode characters such as Kelvin sign can change filtering results.
- List-backed custom blocklists may retain duplicates, which do not change generated IDs.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_sqids_encode.py
./tests/run.sh ./pystachy "jit aot" tests/port_sqids_encode.py tests/port_sqids_blocklist.py
```

The differential tests cover upstream vectors, round trips through 64-bit limits, alphabet/minimum-length errors, blocklist filtering and blocked-ID retries.

Cases: [port_sqids_encode.py](../../tests/port_sqids_encode.py), [port_sqids_blocklist.py](../../tests/port_sqids_blocklist.py).

<a id="speed"></a>

## Performance snapshot

A recorded 100,000-ID encode/decode run was **4.3× faster** by wall time than CPython 3.13.16 on upstream. The same snapshot used more peak RSS (36 MB versus 12 MB); compilation does not reduce memory for every workload.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from sqids 0.5.2; license: MIT.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="sqids-052-ported-to-pystachy"></a>
