# pyfiglet 1.0.4: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `pyfiglet-1.0.4.tar.gz`. License: MIT; bundled FIGlet fonts: BSD-3-Clause; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `db9c9940ed1bf3048deff534ed52ff2dafbbc2cd7610b17bb5eca1df6d4278ef`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `bae593a5b013824c47412db63fb9b66c943b6b9cb0a940e0b785690ce3fb497f` | 58 regions |
| `version.py` | `b611991d8ea92cf84973a0b06018d4690ea91b12e1c0f329fe98e862c8b0bc8e` | none |
| `fonts/standard.flf` | `398a52d40da3ec217ce3673f532eb8e2303023369cfa0dc27b11ff43cc306a4f` | none: a string of `_fontdata.py` |
| `fonts/slant.flf` | `0a1f6ebfa9b0a1658107765d5273f537e2a626c79a6fb431e1ca1e5330a74f2a` | none: a string of `_fontdata.py` |
| `fonts/small.flf` | `6326d8a718cb57689d5eaa98d301b9297ef6f6300279635b901532a2f3d6aadf` | none: a string of `_fontdata.py` |

## Adaptation record

- Three unmodified font files are embedded byte-for-byte in `_fontdata.py`; the FIGlet BSD license is reproduced in `THIRD_PARTY_NOTICES`.
- Methods/fields receive types, properties become methods, and the glyph-loading closure becomes `_load_char()`.
- String operations replace the narrow font-parser regular expressions. `_chars()` decodes UTF-8 sequences while preserving the port’s raw-byte behavior at invalid sequences.
- The renderer returns plain strings rather than the `str` subclass, and explicit parameters replace keyword forwarding in the exposed API.

### Font licensing

**The fonts' license.** The three fonts are FIGlet's, and their comment lines name their authors:
"Standard by Glenn Chappell & Ian Chai 3/93 -- based on Frank's .sig", "Slant by Glenn Chappell
3/93 -- based on Standard" and "Small by Glenn Chappell 4/93 -- based on Standard", modified by
John Cowan for FIGlet 2.2 (the standard font's Latin-2 to Latin-5 letters), by Paul Burton in
12/96 (all three) and by patorjk in 2012 (the standard font's U+0CA0). Each header grants:
"Permission is hereby given to modify this font, as long as the modifier's name is placed on a
comment line." FIGlet's repository (github.com/cmatsuoka/figlet) has them in its `fonts/`, under
its 3-clause BSD license ("Copyright (C) 1991, 1993, 1994 Glenn Chappell and Ian Chai", and later
holders), with the same glyphs as pyfiglet's copies, which differ in their first line (and the
standard font in three comment lines and a last line of blanks). pyfiglet's repository keeps them
among its `fonts-standard`, the fonts that its README says "have a clear redistribution license",
and its sdist ships them beside its MIT `LICENSE`. The port embeds them unmodified, and
`THIRD_PARTY_NOTICES` reproduces FIGlet's license.


## Validation snapshot

`tests/port_pyfiglet_render.py` runs the cases of pyfiglet's own test, `pyfiglet/test.py` in the
sdist, which renders four texts in each font with one `Figlet` object whose `setFont()` changes
and compares each with what the C `figlet` prints: one word, a text cut at its spaces, a long word
cut at its last character, and an explicit new line, for the three embedded fonts, printed line by
line with `repr()` as `test.py`'s `dump()` does; then `test.py`'s four banners, in the default
font at the default width of 80. `tests/port_pyfiglet_edges.py` takes the edge cases the port and
its verifier met: what the parser reads from each font (header fields, comment, glyph counts and
widths, the 7 German letters and the Latin Extended-A glyphs, and the glyph of `@`, whose rows hold
`@`s besides their end marks); every justification, a justification and a direction pyfiglet does
not know (`'middle'`, `'sideways'`); right to left; wrapping at blanks and inside a word, at widths
around the glyph `M`'s 9 columns and at 9223372036854775807; `CharNotPrinted` at widths 8, 0 and
-5; new lines, tabs, carriage returns, blanks and empty text; Latin-1 and Latin Extended-A letters,
and `€`, an emoji and CJK characters, which no font has; text made with `chr()`, every glyph of the
standard font above `~` and bytes that start no UTF-8 sequence; every printable ASCII character in
each font; `str()` of a font; `setFont()`; `FontNotFound` for a missing name, a path and `''`; and
a `FontNotFound` that nothing catches, which ends the program as CPython reports it
(`tests/port_pyfiglet_edges.err`).
Each of its parts is a function, so that the fonts it loads are garbage when it returns.

`tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under CPython against the
unmodified upstream package, both print exactly what they print against this port. Both pass JIT
and AOT with `PYSTACHY_IRCHECK=1`, with the native compiler and the CPython-hosted one, with
`PYSTACHY_OPT=-all`, and `tests/run.sh` passes as a whole (1,935 passed, 0 failed). They stay
small in the gc-stress form of `make verify` (the compiler collecting every 1,000 allocations, the
program at every allocation), where the JIT run and the AOT build and run of `port_pyfiglet_render`
take 6.2 s of CPU together (2.5 s, 1.1 s and 2.6 s) and those of `port_pyfiglet_edges` 8.7 s
(2.9 s, 1.4 s and 4.4 s). Without gc-stress, each JIT run takes 0.2 s of CPU, each AOT build
1.0 s and 1.3 s, and each AOT run 0.02 s and 0.03 s. Under gc-stress, each collection scans what
is live, and a parsed standard font holds about 1,400 strings (236 glyphs of 6 rows): in a probe,
a standard font kept in a module-level variable made five renderings in the small font after it
3.5 times as costly (0.22 s to 0.76 s of CPU), and a `del` of the variable did not undo it
(0.76 s; the runtime's `del` of a global marks it unbound and keeps the object, where binding the
variable to another object frees it). The edges test took 11.7 s before its parts became
functions.

## Benchmark snapshot

**Run time.** The headline workload: a `Figlet` made for each of the three fonts (which loads and
parses it) and a 220-character text rendered at width 200, 40 times each, every other time
centred; and the same text rendered 80 times in each font by three `Figlet`s made once. Median of
5 runs, wall clock with process start-up and CPU time, on a 4-core x86-64 VM at load 0.8, with a
compiler built from main 4dc548a:

| | load and render: wall | CPU | render only: wall | CPU |
|---|---:|---:|---:|---:|
| Pystachy AOT executable, this port | 0.246 s | 0.245 s | 0.369 s | 0.369 s |
| CPython 3.13.16, unmodified pyfiglet 1.0.4 | 0.671 s | 0.670 s | 0.991 s | 0.989 s |

That is 2.7 times faster with the font loads and 2.7 times rendering only, in wall clock and in
CPU time alike. Earlier sets of runs, on the VM at load 4 to 12, gave CPU ratios of 2.6 to 2.7 for
both, and wall-clock ratios of 2.2 to 2.7. pyfiglet has no C extension, so CPython runs the same
Python code; but where the port reads its fonts from strings in the executable, upstream reads
each font's file (28 KB for the standard font) and checks whether it is a zip archive every time a
`Figlet` is made. The rendering itself is string work: each glyph row joined to the line by
slicing and concatenation, and `getCharAt()` copying the text's list of code points (`len(list(
self.text))`) for each character.

**Build time and size.** `pystachy build` of a program that imports pyfiglet and prints
`figlet_format("Hi")` takes 1.0 s of CPU, against 0.16 s for `print(1)`, and makes a 178 KB
executable (28 KB for `print(1)`) that holds the three fonts (56 KB of text) and needs no files at
run time.
