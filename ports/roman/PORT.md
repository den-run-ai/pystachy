# roman 5.2

Convert integers 0–4999 to Roman numerals and back, with validation and the upstream exception hierarchy.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/roman/) · [License](LICENSE)

```python
from roman import toRoman, fromRoman

print(toRoman(1987))
print(fromRoman("mcmlxxxvii"))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `toRoman(int)`, `fromRoman(str, special_case: bool = True)`, numeral mapping and error classes.
- ASCII upper/lowercase numerals, `N` for zero and upstream’s final-newline validation behavior.
- The argparse-based CLI is outside the validated port coverage. `romanNumeralPattern` is replaced by an internal boolean validator.

<a id="deviations-it-hits"></a>

## Compatibility

- Invalid argument types are rejected during compilation rather than following CPython’s dynamic coercion/error paths.
- ASCII case conversion agrees; non-ASCII text uses Pystachy’s byte-oriented rules. CPython accepts dotless `ı` as `I`, while the port rejects it.
- Values beyond checked 64-bit integers overflow before the converter can raise `OutOfRangeError`.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_roman_convert.py
./tests/run.sh ./pystachy "jit aot" tests/port_roman_convert.py tests/port_roman_validate.py
```

The tests cover upstream examples/errors, every integer 1–4999 in both directions, lowercase forms, pattern boundaries and exceptions.

Cases: [port_roman_convert.py](../../tests/port_roman_convert.py), [port_roman_validate.py](../../tests/port_roman_validate.py).

<a id="speed"></a>

## Performance snapshot

A recorded workload of about one million conversions in each direction was **3.7× faster** than CPython 3.13.16 on upstream (**4.7×** on the same adapted code). The validator uses a Python function instead of upstream’s C regex engine.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from roman 5.2; license: ZPL-2.1.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="roman-52-ported-to-pystachy"></a>
