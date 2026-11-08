# Pystachy status check, 2026-11-08

This branch holds evidence about main `ce8c887` (v0.4.0-alpha.1); it is not for merging. Main
ignores `research/`. Claude Code helped prepare the check, its reproducers and the
[issue drafts](issues.md). Every finding below was reproduced against a fresh `make` of
`ce8c887`, on Linux x86-64 with LLVM 18.1.3 and CPython 3.13.18.

## Summary

- **Recap:** every count in the week's recap checks out: 139 PRs opened and 117 merged,
  17 issues opened and 24 closed, 25 open PRs (24 drafts) and 227 open issues. The final
  main CI run passed 68 of 70 jobs, with two intentional skips. Three corrections follow.
- **Bugs:** no P0 was found. Eight untracked defects were reproduced, three of them narrow
  P1s, and #50 still reproduces. Most sit on the `lli` launch path, which every
  `pip install pystachy` user takes.
- **What held up:** the riskiest code that shipped this week, the #1125/#1122 bounds-check
  removal and the default-on program cache, survived adversarial probing.
- **Structural risks:** compiler growth (+37% in 18 days), CI jobs near the 15-minute cap,
  and a PyPI package that ships only the slow hosted compiler.

## Corrections to the recap

- **Main CI on `3dbae38` failed, though GitHub shows the run as cancelled.**
  `verify (gc-jit-1)` hit the 15-minute cap and both `make verify` aggregators failed. #1163
  split the GC jobs, raising the run from 66 to 70 jobs.
- **#1156's Lint run timed out after 15m15s;** no newer push superseded it.
- **#1154 is not just tracker cleanup.** The overwrite is fixed, but the issue's "match
  CPython and AOT" criterion is not met (drafts 2 and 4).
- **Milestones are stale.** Only v0.2.0 (16 items) and v0.3.0 (2 items) exist, and both are
  still open after shipping. No open issue has a milestone.

## Findings

Run `python3 -I research/status-20261108/repro/run.py` from the checkout root; it exits 1
while anything reproduces.

| Severity | Finding | Paths | Draft |
|---|---|---|---|
| P1, opt-in | With a dynamic-`Any` iterator, `zip` reads list items after calling `__next__`. A `__next__` that writes the list gives `400.0` where CPython gives `10.0`. | JIT, AOT | 1 |
| P1, narrow | MCJIT's jitdump file takes over a closed fd 0, 1 or 2. A closed stdin reads `''` and the program exits 0. | `PYSTACHY_JIT_CODEGEN=0` | 2 |
| P2 | Each MCJIT run leaves a jitdump file behind. | `PYSTACHY_JIT_CODEGEN=0` | 2 |
| P1, narrow | An extensionless file imports as a namespace package, so `except ImportError` fallbacks take the wrong branch. | JIT, AOT | 3 |
| P1, narrow | An ignored SIGINT is not preserved, so Ctrl-C raises `KeyboardInterrupt` (#50). | hosted, cache off, MCJIT | comment |
| P2 | JIT inputs leak on the lowest free fds (`/dev/fd/3` holds LLVM bitcode), and children inherit them. | hosted, cache off, MCJIT, embedding | 4 |
| P2 | The program-cache key omits `PYSTACHY_DEBUG_LINES`. | cached runs | 5 |
| P2 | The program-cache key treats an empty `PYSTACHY_JIT_INLINE=` as unset. | cached runs | 5 |
| P2 | `input()` with a closed stdin raises `EOFError`; CPython raises `RuntimeError`. | JIT, AOT | 6 |

## What held up

- **Bounds-check removal (#1125, #1122):** no needed check was removed. Probes covered
  implicit dunder calls, overrides, wrappers, recursion, and rebinding of globals, fields,
  cells and parameters. Callback clones that shrink the list kept their checks. Reads that
  were rewritten matched CPython in JIT, in AOT and under GC stress.
- **Program cache:** no stale reuse. Probes covered same-size edits with restored mtimes,
  shadowing modules, namespace/regular package flips, retargeted symlinks, edits to `lib/`,
  the runtime and headers, concurrent edited launches, and 14 random SIGKILLs.
- **Descriptors (#1162):** inherited pipes on fds 3–10, 63, 64, 200 and 1000 survive every
  launch path.
- **Other spot checks:**
  - int64 overflow raises and never wraps.
  - Mutation during dict, set or list iteration matches CPython, as does a dict or set that
    `__eq__` resizes mid-lookup, including under GC stress.
  - #1131's optional numeric slots match CPython.
  - v0.3.1's pipe reads match across split UTF-8 and `\r\n`.
  - Generators in `zip` keep CPython's order.

## Gaps, performance and architecture

- **Language:** no `async`/`await`, `match`, general multiple inheritance, `complex`,
  `bytearray`/`memoryview`, `__del__`, `eval`/`exec` or exception groups. `int` is checked
  64-bit unless a module opts in, and dynamic `Any` is partial and opt-in.
- **Library:** no starting threads, and no `subprocess`, `socket`, `asyncio`, `hashlib`,
  `zlib`, `pickle`, `xml` or `decimal`. Native C extensions work only through the CPython
  bridge.
- **Distribution:** PyPI ships a pure-Python wheel, the hosted compiler, with no native
  wheels (#998). The program cache is Linux-only. `docs/install.md` never mentions the PyPI
  install that the README leads with, and `docs/language.md` still cites the alpha.4 notes.
- **Launch latency:** timed on this VM with the JSON-repair port.

  | Launch | Time |
  |---|---|
  | CPython | 0.04 s |
  | Native cache hit | 0.05 s |
  | Native uncached | 1.2 s |
  | Native miss after an edit | 1.6–1.7 s |
  | Hosted (PyPI path) | 2.5 s every run |
  | AOT build | 7.1 s |
  | First use of a fresh cache | 15.7–18.1 s |

- **Growth:** compiler plus runtime source grew from 55.4k lines (Oct 21) to 76.0k (Nov 8),
  and the compiler's IR from 639.5k to 878.5k lines. `dynamic.py` (+3.8k) and `bigints.py`
  (+1.5k) are opt-in prototypes that every build compiles. `make` takes 3m51s and runs
  essentially single-threaded.
- **Compiler state:** `Gen` holds 275 mutable fields (252 on Oct 21) across 1,179 methods,
  and speculative passes must restore them all. #767 and #801 are open, and #816 shows why
  batching declines is unsound.
- **Runtime model:** typed and dynamic-`Any` semantics still differ (#803, #858). The
  collector is conservative, batched and non-moving, with no finalizers (#715, #1095).
- **CI budget:** about 482 runner-minutes per main push. Nine x86-64 jobs take 10–12.3 of
  their 15 minutes, and `gc-self` takes 7.7 of its 10. Six of the last ten Variants runs
  timed out (#1083).
- **Process:** only 4 of the 117 merged PRs carry automated review findings, all resolved.
  #1117, #1122, #1125, #1130 and #1131 merged as drafts through integration PRs, which did
  run exact-main CI. v0.3.0 shipped 66 minutes after its release candidate.
- **Tracker:** no P0/P1 labels are in use (35 `bug`, 5 P2, 4 P3). #743 is a stale
  non-draft PR.

## Handoff

- **Branch:** `claude/happy-franklin-mc6j4c` is main `ce8c887` plus this directory. There is
  no PR; do not merge.
- **Changed behavior:** none. No compiler, runtime, library, test or documentation changes.
- **Ran:**
  - `make`: compiler and runtime fixed points at 878,455 and 19,907 IR lines;
  - focused CPython-versus-JIT/AOT probes, including GC stress;
  - the runner below, which took 72 s;
  - ruff 0.16.9 on these files;
  - `tools/check_submission.validate` on every draft.
- **Not run:** `make verify`, `make test`/`test-py`, `make lint`, `check-recordings`,
  `irsame`, full GC/UBSan groups, macOS or ARM64, or the recap's research measurements
  (BPE, ThinLTO, workers, JSON-repair RSS, mypyc).
- **Live work:** none. Three probe agents finished; no watches or scheduled tasks remain.
  Their raw logs were local to the session container.
- **Unverified:** macOS presumably shares the `lli`-path gaps, since the cache is Linux-only.
  Timings are single runs on a shared 4-vCPU VM.
- **Next:**
  1. File the six issues and two comments from the drafts.
  2. Make `lli` launches close their inputs and keep an inherited SIGINT disposition, which
     covers every PyPI user.
  3. Key the cache on all compile settings.
  4. Document the PyPI install, or ship native wheels.
  5. Recover CI headroom by cutting compiler cost rather than adding jobs.
  6. Close the stale v0.2.0 and v0.3.0 milestones, add v0.4.0 scope, and narrow #998.

Runner output on `ce8c887`:

```text
REPRODUCES  zip-dynamic-any zip_dynany.py: CPython '10.0'; JIT '400.0'; AOT '400.0'
REPRODUCES  zip-dynamic-any zip_dynany_clear.py: CPython '1.0'; JIT 'IndexError: list index out of range'; AOT 'IndexError: list index out of range'
REPRODUCES  mcjit-closed-stdin: exit 0, "read 0 ''"
REPRODUCES  mcjit-dump-leftover: 1 jitdump file(s) left in TMPDIR
REPRODUCES  extensionless-import: CPython 'fallback'; JIT 'imported'
REPRODUCES  jit-input-fd-leak (native, cache off): CPython 'fd3 FileNotFoundError'; Pystachy 'fd3 4243c0de'
REPRODUCES  jit-input-fd-leak (hosted (PyPI path)): CPython 'fd3 FileNotFoundError'; Pystachy 'fd3 4243c0de'
OK          jit-input-fd-leak (control: native, cached): CPython 'fd3 FileNotFoundError'; Pystachy 'fd3 FileNotFoundError'
REPRODUCES  cache-key-debug-lines: PYSTACHY_DEBUG_LINES=1 launch was a hit
REPRODUCES  cache-key-empty-jit-inline: cached exit 0, uncached exit 1
REPRODUCES  input-closed-stdin: CPython 'RuntimeError lost sys.stdin'; JIT 'EOFError'; AOT 'EOFError'
REPRODUCES  sigint-ignored #50 (native, cache off): CPython 'SIGINT ignored'; Pystachy 'SIGINT caught'
REPRODUCES  sigint-ignored #50 (hosted (PyPI path)): CPython 'SIGINT ignored'; Pystachy 'SIGINT caught'
REPRODUCES  sigint-ignored #50 (MCJIT): CPython 'SIGINT ignored'; Pystachy 'SIGINT caught'
OK          sigint-ignored #50 (control: native, cached): CPython 'SIGINT ignored'; Pystachy 'SIGINT ignored'
OK          sigint-ignored #50 (control: AOT): CPython 'SIGINT ignored'; Pystachy 'SIGINT ignored'
13 of 16 checks reproduce
```
