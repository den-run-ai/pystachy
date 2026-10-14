# sgp4 2.27

Propagate Earth-satellite orbits from two-line element sets with the pure-Python SGP4/SDP4 implementation, returning TEME position and velocity.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/sgp4/) · [License](LICENSE)

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `Satrec.twoline2rv()`, `sgp4()`, `sgp4_tsince()` and `sgp4init()` with WGS72OLD/WGS72/WGS84 gravity constants.
- Near-Earth and deep-space/resonant propagation; the tested Julian-date, orbital-element and Alpha-5 helpers. Pass floating-point time arguments to the annotated propagation methods.
- The C++ accelerator, NumPy array API, legacy `Satellite` API, datetime convenience helpers, TLE/OMM export and OMM import are outside the port’s coverage.
- Use `sat.no_kozai` for the omitted `no` property and `from_alpha5(sat.satnum_str)` for the omitted `satnum` property.

<a id="deviations-it-hits"></a>

## Compatibility

- TLE parsing requires ASCII and preserves fixed columns. It does not verify TLE checksums; checksum helpers are outside the validated API.
- Native checked integers constrain extreme epochs. Negative mean-motion fractional powers raise `ValueError`, where CPython reaches a later complex-number `TypeError`.
- `io.twoline2rv()` stores integer `ephtype`/`revnum` fields, and the legacy datetime-valued `epoch` field is omitted.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_sgp4_verify.py
./tests/run.sh ./pystachy "jit aot" tests/port_sgp4_verify.py tests/port_sgp4_api.py
```

Committed tests embed selected official Vallado verification vectors, covering SGP4, resonant/deep-space orbits and error cases; API tests add malformed TLEs and numeric boundaries. A separate historical probe reproduced all 700 official output lines.

Cases: [port_sgp4_verify.py](../../tests/port_sgp4_verify.py), [port_sgp4_api.py](../../tests/port_sgp4_api.py).

<a id="speed"></a>

## Performance snapshot

A recorded AOT run of 518,400 ISS/Molniya propagations was **8.1× faster** by wall time than CPython 3.13.16 on the pure-Python implementation. The package’s C++ extension was not compared.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from sgp4 2.27; license: MIT.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="sgp4-227-ported-to-pystachy"></a>
