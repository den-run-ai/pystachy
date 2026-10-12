# Library ports: the evaluation records and their checks

The evidence behind #132, the evaluation of which PyPI packages and stdlib modules Pystachy can compile, and #171, what the ports teach, so that their numbers can be recomputed. It sits on the `claude/ports-research` branch, as `research/ffi/` sits on `claude/ffi-research`; it is not meant for main.

| file | what |
|---|---|
| `packages.json` | the 115 evaluation records (91 PyPI packages, 24 stdlib modules) |
| `hubs.json` | the stdlib-hub probe: which missing modules block `import X`, and the stub experiment (9 of 91 → 14) |
| `tables.py`, `tables.out` | #171 §4: blocked packages per milestone, the unblocking table, the kinds of M4 blockers |
| `port_markers.py`, `port_markers.out` | #171 §2: the 626 `Pystachy port:` markers of the 14 ports, by cause, with keyword rules |
| `census_ports.py`, `census_ports.out` | the check of §2 with `tools/census.py`: each port against the upstream modules it keeps (`tools/port_edits.py`, #182, does it for one port) |

## The records

**How each record was made:**
- An agent per domain tried to port the package's headline use case with the fewest marked edits.
- It compared the JIT and AOT output with CPython running the unmodified upstream, and timed an AOT build against CPython.
- An independent pass re-ran each claim, added harder inputs, and corrected edit counts, divergences and roadmap mappings.

**Fields:**
- `version`, `rank` (30-day PyPI downloads to 2026-10-01) and `core_files`, the headline path;
- `status`: `compiles_with_edits`, `core_subset_with_edits` or `blocked`;
- `edits`, `matches_cpython`, `perf` and `divergences`;
- `blockers`: each with its `roadmap` milestone (`M1`–`M7`, `hub:NAME` for M6, or another issue), `on_core_path`, and `small_edit_workaround`;
- `verify`: the second pass's notes.

Local paths in the notes read `<scratch>/`.

**Caveat:** the blocker judgments, above all whether a small edit works around a blocker, are the agents' and the second pass's, not mechanical. The census check below is the mechanical part.

## The census check of #171 §2

`census_ports.py` runs the census on each port and on the upstream modules it keeps, then sums the blockers the edits removed by milestone:

| milestone | markers (#171) | census blockers removed |
|---|---:|---:|
| M2 classes | 221 (35%) | 127 (30%) |
| M7 long tail | 110 (18%) | 120 (28%) |
| M4 dynamic values | 87 (14%) | 21 (5%) |
| M3 functions as values | 69 (11%) | 58 (13%) |
| M1 loader, annotations | 55 (9%) | 1 (0.2%) |
| M6 stdlib | 52 (8%) | 97 (23%) |
| M5 exceptions | | 6 (1.4%) |

A marker is an edited line; a census blocker is one use in one unit. Both put classes first. They differ in three places:
- **M4:** most dynamic-value edits are about types (a rebound variable, `None`, an `Any` parameter), which an AST scan can't see.
- **M6:** `import_other` also counts a package's relative imports of its own modules, which the loader compiles.
- **M1:** the census has no blocker for Python 2 shims or for tuples indexed by a variable.

## Reproducing

```sh
python3 research/ports/tables.py
python3 research/ports/port_markers.py ports/jdcal ports/pylev ports/qrcode origin/claude/port-convertdate ...  # every port
# the sdists the ports name in PORT.md, unpacked into sdists/NAME-VERSION/:
pip download --no-deps --no-binary :all: -d sdists qrcode==8.2   # and so on for each port
python3 research/ports/census_ports.py sdists
```
