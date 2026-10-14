# qrcode 8.2

Generate QR matrices and terminal text from strings, including segment optimization, Reed–Solomon error correction and selection among the eight masks.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/qrcode/) · [License](LICENSE)

```python
from qrcode import QRCode

qr = QRCode(border=1)
qr.add_data("https://example.com")
qr.make()
qr.print_ascii()
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `QRCode`, `add_data(str)`, `make()`, `get_matrix()`, `print_ascii()` and the underlying encoder utilities.
- Numeric, alphanumeric and UTF-8 byte modes; all four correction levels and QR versions 1–40.
- PIL/PyPNG/SVG images, styled images/logos, `make_image()`, the `qr` CLI and `print_tty()` are outside this port’s API.
- Input is `str`, rather than upstream’s bytes, coercible values or prebuilt `QRData` objects.

<a id="deviations-it-hits"></a>

## Compatibility

- `version` and `mask_pattern` are fields. Invalid assignments are checked on the next `make()`; reading an unset version returns `None` rather than fitting one.
- `get_matrix()` is typed as `list[list[bool | None]]`; completed modules have boolean values. `optimal_data_chunks()` returns a list rather than a generator.
- Text literals encode the same UTF-8 data as upstream. `chr()` values 128–255 are raw bytes in Pystachy, and lone-surrogate behavior differs.
- `print_ascii(tty=True)` always raises `OSError("Not a tty")`.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_qrcode_encode.py
./tests/run.sh ./pystachy "jit aot" tests/port_qrcode_encode.py
```

The differential test checks matrices/text, every mask and correction level, UTF-8 inputs, capacity boundaries, chunk optimization, setter validation and error paths.

Cases: [port_qrcode_encode.py](../../tests/port_qrcode_encode.py).

<a id="speed"></a>

## Performance snapshot

A recorded AOT run creating 400 fitted/masked codes was about **8.5× faster** than CPython 3.13.16 on upstream. The adapted Python chunker is slower than upstream’s C regex path when both run under CPython.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from qrcode 8.2; license: BSD-3-Clause with pyqrnative MIT notice.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="qrcode-82-ported-to-pystachy"></a>
