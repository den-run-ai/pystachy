# iniconfig 2.3.1: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `iniconfig-2.3.1.tar.gz`. License: MIT; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `67f4b9c50da0dedf52af349e7749a80a9057a5031199791b906c3bb3ae878960`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `exceptions.py` | `9a2a50fda3310fd0af4af156375a135d8e10b919ca00c6757f7b027668c34d4d` | none |
| `_parse.py` | `15824a78105b52aa9ed414ce6ad073967c73be7ea5ae9d991a0df97a6e0cc2e1` | 1 line |
| `__init__.py` | `bb1c9017eea0053a104bd0703f3d8d13e7b9a854e4a364ee765ad64da7220819` | 5 methods |

## Adaptation record

- `_parse.py` spells the byte-order mark as `"\ufeff"` instead of a named Unicode escape.
- The two `get()` implementations retain string results/defaults and omit generic conversion callbacks.
- Section/config iteration sorts `(line, name)` pairs and returns list-backed iterators; `items()` materializes its pairs.
- `exceptions.py` is unchanged. `_version.py` is omitted because nothing imports it.

## Validation snapshot

`tests/port_iniconfig_parse.py` and `tests/port_iniconfig_api.py` run the cases of iniconfig's
own `testing/test_iniconfig.py` as programs, and `tests/run.sh` compares what they print with
CPython's, JIT and AOT. They leave out what the edits remove (`convert=int`, non-`str` defaults)
and `IniConfig(data=...)` without a path, which CPython rejects with a `TypeError` at run time and
Pystachy at compile time. Run under CPython against the unmodified upstream package, both print
exactly what they print against this port.
