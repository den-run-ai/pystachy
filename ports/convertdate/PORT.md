# convertdate 2.5.1

Convert dates between Gregorian, Julian, Hebrew, arithmetical Islamic, Coptic, Indian civil, Armenian, Positivist and Mayan calendars.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/convertdate/) · [License](LICENSE)

```python
from convertdate import gregorian, islamic

jd = gregorian.to_jd(2024, 1, 1)
print(islamic.from_jd(jd))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- Calendar conversions, month lengths, leap years, month calendars and selected holiday functions.
- Julian day counts, ordinal dates, and the tested ISO week helpers.
- The astronomical Bahá’í, French Republican and Persian calendars and the Dublin module are omitted.
- Date/time objects, calendar formatting, Mayan generators and the `Holidays` convenience class are outside the tested port coverage.

<a id="deviations-it-hits"></a>

## Compatibility

- `_calendar.IllegalMonthError` derives from `IndexError`, rather than both `IndexError` and `ValueError`. Catch `IndexError` for its invalid-month errors.
- `hebrew.month_days()` omits upstream’s deprecation warning. The Islamic holiday functions’ upstream `eve=True` bug is outside the supported test cases.
- Calendar names print correctly, but indexing and measuring non-ASCII text follows Pystachy’s UTF-8 byte rules. Extremely large years can overflow checked 64-bit arithmetic.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_convertdate_calendars.py
./tests/run.sh ./pystachy "jit aot" tests/port_convertdate_calendars.py tests/port_convertdate_holidays.py
```

The differential tests cover calendar round trips, epochs, leap years, holiday variants and error paths against CPython.

Cases: [port_convertdate_calendars.py](../../tests/port_convertdate_calendars.py), [port_convertdate_holidays.py](../../tests/port_convertdate_holidays.py).

<a id="speed"></a>

## Performance snapshot

A recorded AOT run of 73,000 multi-calendar conversions was about **25× faster** than CPython 3.13.16 on upstream.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from convertdate 2.5.1; license: MIT.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="convertdate-251-ported-to-pystachy"></a>
<a id="8s-fargs"></a>
