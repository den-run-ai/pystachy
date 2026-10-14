# jdcal 1.4.1

Convert proleptic Gregorian and Julian dates to split Julian dates and back. Keeping a Julian date as two floats preserves the day fraction’s precision.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/jdcal/) · [License](LICENSE)

```python
import jdcal

jd = jdcal.gcal2jd(2000, 1, 1)
print(jdcal.jd2gcal(jd[0], jd[1]))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- All four conversion functions, `ipart()`, `is_leap()`, `MJD_0` and `MJD_JD2000`.
- Use integer year/month/day arguments; explicitly convert other inputs with `int()`. Inverse conversions accept the tested integer and floating-point Julian-date parts.
- The single upstream module is packaged as `ports/jdcal/__init__.py`.

<a id="deviations-it-hits"></a>

## Compatibility

- `is_leap()` returns a `bool`. Upstream sometimes returns a nonzero float, so its truth value agrees but printing/equality can differ.
- Very large calendar arithmetic and float-to-year conversions can exceed Pystachy’s 64-bit integer range. These limits are far outside ordinary calendar dates.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_jdcal_convert.py
./tests/run.sh ./pystachy "jit aot" tests/port_jdcal_convert.py tests/port_jdcal_extremes.py
```

The tests cover both calendars, round trips, normalized out-of-range dates, day fractions, Excel serial dates and numeric extremes.

Cases: [port_jdcal_convert.py](../../tests/port_jdcal_convert.py), [port_jdcal_extremes.py](../../tests/port_jdcal_extremes.py).

<a id="speed"></a>

## Performance snapshot

A recorded AOT workload of 2,688,000 four-function round trips was about **19× faster** than CPython 3.13.16 on upstream; ERFA/astropy C routines were not compared.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from jdcal 1.4.1; license: BSD-2-Clause.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="jdcal-141-ported-to-pystachy"></a>
