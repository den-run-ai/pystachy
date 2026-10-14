# Third-party library ports

These are adapted upstream libraries, kept as valid Python and compiled through Pystachy’s
JIT and AOT paths. Each port exposes a documented subset; compiling a port does not imply
support for its complete upstream package or dependencies.

## Choose a port

| Port | Upstream | Validated use |
|---|---|---|
| [convertdate](convertdate/PORT.md) | 2.5.1 | Arithmetic calendar conversions and selected holidays |
| [iniconfig](iniconfig/PORT.md) | 2.3.1 | INI parsing and string-valued configuration access |
| [jdcal](jdcal/PORT.md) | 1.4.1 | Gregorian/Julian ↔ split Julian dates |
| [ordered-set](ordered_set/PORT.md) | 4.1.0 | Insertion-ordered sets of strings |
| [pyaes](pyaes/PORT.md) | 1.6.1 | AES blocks with integer-list keys/data |
| [pyfiglet](pyfiglet/PORT.md) | 1.0.4 | ASCII banners in three embedded fonts |
| [pylev](pylev/PORT.md) | 1.4.0 | Edit distances for ASCII strings and typed sequences |
| [qrcode](qrcode/PORT.md) | 8.2 | QR matrices and terminal text from strings |
| [roman](roman/PORT.md) | 5.2 | Roman numeral conversions |
| [sgp4](sgp4/PORT.md) | 2.27 | Pure-Python SGP4/SDP4 orbit propagation |
| [snowballstemmer](snowballstemmer/PORT.md) | 3.1.1 | ASCII English Porter2 and Porter stemming |
| [sortedcontainers](sortedcontainers/PORT.md) | 2.4.0 | Sorted integer lists |
| [sqids](sqids/PORT.md) | 0.5.2 | URL-safe IDs from nonnegative integer lists |
| [tomli-w](tomli_w/PORT.md) | 1.2.0 | TOML text from homogeneous typed documents |
| [wcwidth](wcwidth/PORT.md) | 0.9.2 | Unicode terminal-cell widths |

## Compile and run

Build Pystachy using the [quick start](../README.md#quick-start). Add `ports` to the module
path for a program that imports one of these packages:

```sh
PYSTACHY_PATH=ports ./pystachy run program.py
PYSTACHY_PATH=ports ./pystachy build program.py -o /tmp/program
/tmp/program
PYTHONPATH=ports python3 program.py
```

The CPython command runs the adapted sources and is useful for checking semantics.
An upstream comparison must use the pinned upstream package instead of putting `ports` first.
Read each guide’s coverage and compatibility notes before adopting its API.

## Validation and measurements

Each guide links its differential tests and gives a command to run selected cases through
JIT and AOT. The [testing guide](../docs/testing.md) explains the CPython oracle, deviations
and required verification stages.

Port references retain upstream archive/file SHA-256 pins, licenses, edit rationale and
recorded performance measurements. Those measurements describe specific workloads and
compiler snapshots; they are not promises for current builds or comparisons against every
native accelerator. In particular, faster execution does not imply less memory for every port.

The [standard-library notes](../lib/README.md) cover modules shipped in `lib/`.
The [language guide](../docs/language.md) describes current typing and runtime boundaries.
