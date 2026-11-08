# Issue drafts from the 2026-11-08 status check

Nothing here has been filed. Each draft follows the submission format in
[CONTRIBUTING.md](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/CONTRIBUTING.md#issues-and-pull-requests):

- a title of at most 64 characters;
- a body of at most 200 words and 6,000 characters, counting code and tables;
- the sections `## Problem`, `## Scope`, `## Done when`, in that order, with no checklist;
- links for larger evidence.

Every body passes `tools/check_submission.validate()`; word counts are shown. Bodies end
with an AI-assistance disclosure and carry no tool footer, per AGENTS.md. Every finding
reproduces on main `ce8c887`; run `python3 -I research/status-20261108/repro/run.py`.

Severity: P1 means a silent wrong result or data misdirection in an opt-in or narrow path. P2
means a wrong error, a leak, or a key gap that leaves program output unchanged. No P0 was
found.

### 1. Preserve zip item order with dynamic Any iterators

Labels: `bug`, `priority: P1` · P1, opt-in dynamic `Any` · 150 words

````markdown
## Problem

In a `# pystachy: dynamic-any` module, `zip(xs, it)` calls a dynamic iterator's `__next__` before reading `xs[i]`. CPython reads `xs[i]` first, so a `__next__` that writes or clears `xs` silently changes results. Typed iterator classes and generators keep CPython's order.

## Scope

On main `ce8c887` (Linux x86-64, LLVM 18.1.3, CPython 3.13.18), [this program](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/zip_dynany.py)'s `__next__` sets `XS[self.n] = 100.0`:

```python
def f(a: Any) -> float:
    t = 0.0
    for x, y in zip(XS, a):
        t += x
    return t
```

| `__next__` | CPython | JIT and AOT |
|---|---|---|
| writes `XS` | `10.0` | `400.0` |
| [clears `XS`](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/zip_dynany_clear.py) | `1.0` | `IndexError` |

[`gen_for_seq`](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/src/pystachy_compiler/statements.py#L1881-L1900) runs `pys_dyn_next` during the length tests and reads list items afterwards. Refs #92. Prepared with Claude Code assistance.

## Done when

Dynamic-iterator `zip` takes each argument's item in argument order. Differential JIT/AOT cases for writing and shrinking `__next__`, including GC stress, match CPython.
````

### 2. Keep closed standard streams closed under MCJIT

Labels: `bug`, `priority: P1` · P1 on the opt-in `PYSTACHY_JIT_CODEGEN=0` path, plus a P2 leak · 131 words

````markdown
## Problem

With `PYSTACHY_JIT_CODEGEN=0`, `lli` opens its perf jitdump file (`$TMPDIR/.debug/jit/llvm-IR-jit-*/jit-<pid>.dump`, read-write) on a closed descriptor 0, 1 or 2. A closed stdin then reads as empty, output for a closed stdout is appended to the dump file, and each run leaves its dump file behind.

## Scope

On main `ce8c887` (Linux x86-64, LLVM 18.1.3), with [stdin_read.py](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/stdin_read.py):

```python
import sys
data = sys.stdin.read()
print("read", len(data), repr(data[:4]))
```

`PYSTACHY_JIT_CODEGEN=0 PYSTACHY_PROGRAM_CACHE=0 pystachy run stdin_read.py 0<&-` prints `read 0 ''` and exits 0. AOT and ORC JIT report `OSError: [Errno 9] Bad file descriptor`. ORC, cached and hosted runs leave no dump files. Follows #1154. Prepared with Claude Code assistance.

## Done when

MCJIT launches keep closed standard streams closed and leave no dump files, matching ORC and AOT. `tools/jitfdprobe.py` covers MCJIT's closed streams.
````

### 3. Skip extensionless files when resolving imports

Labels: `bug`, `priority: P1` · P1, narrow · 111 words

````markdown
## Problem

A regular file without an extension satisfies `import name` as a namespace-package portion. CPython raises `ModuleNotFoundError`, so `except ImportError` fallbacks silently take the other branch.

## Scope

On main `ce8c887`, with a one-line text file `plainname` beside [main.py](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/extless/main.py):

```python
try:
    import plainname
    print("imported")
except ImportError:
    print("fallback")
```

CPython 3.13.18 prints `fallback`; JIT and AOT print `imported`, with or without the program cache. [`Loader.filepath`](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/src/pystachy_compiler/loader.py#L1048-L1051) accepts any existing path as a portion through [`tracked_exists`](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/src/pystachy_compiler/program_cache.py#L243-L250), an `os.path.exists` probe. Prepared with Claude Code assistance.

## Done when

Only directories become namespace-package portions; extensionless files are ignored as in CPython. A differential case covers the fallback, and namespace-package and program-cache import probes still pass.
````

### 4. Close JIT input descriptors before running programs

Labels: `bug`, `priority: P2` · P2; affects every PyPI install · 144 words

````markdown
## Problem

Launches through `lli` leave the deleted program bitcode, runtime `.so` or `.o`, and `pyembed.o` open on the lowest free descriptors without close-on-exec. Programs and their children see them: opening `/dev/fd/3` returns LLVM bitcode where CPython raises `FileNotFoundError`.

## Scope

On main `ce8c887` (Linux x86-64, LLVM 18.1.3), [fd3.py](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/fd3.py) prints `fd3 4243c0de` under hosted JIT (the PyPI install path), `PYSTACHY_PROGRAM_CACHE=0`, MCJIT and embedding. CPython, AOT and cached runs print `fd3 FileNotFoundError`. `/proc/self/fd` shows two extra descriptors, three with embedding.

The [launcher](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/src/pystachy_compiler/driver.py#L1141-L1161) opens these inputs inheritable so `lli` can read `/dev/fd/N`; nothing closes them before user code runs. #1162 fixed the overwrite reported in #1154; this leak predates it. Prepared with Claude Code assistance.

## Done when

Programs launched through `lli` see the same descriptor table as CPython and AOT on every path, their children inherit none of these files, and `tools/jitfdprobe.py` rejects unexpected descriptors.
````

### 5. Key cached programs on every compile-time setting

Labels: `bug`, `priority: P2` · P2; program output unaffected · 133 words

````markdown
## Problem

The native program cache omits `PYSTACHY_DEBUG_LINES` from its key and treats an empty setting as unset. A hit can return an executable without the requested line tables, or run a launch that uncached compilation rejects.

## Scope

On main `ce8c887` with `PYSTACHY_PROGRAM_CACHE_TRACE=1` and [cache_prog.py](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/cache_prog.py):

```sh
pystachy run cache_prog.py                        # stored
PYSTACHY_DEBUG_LINES=1 pystachy run cache_prog.py # hit, no .debug_* sections
PYSTACHY_JIT_INLINE= pystachy run cache_prog.py   # hit, exit 0
PYSTACHY_JIT_INLINE= PYSTACHY_PROGRAM_CACHE=0 pystachy run cache_prog.py  # exit 1
```

[`gen.py`](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/src/pystachy_compiler/gen.py#L1309) reads `PYSTACHY_DEBUG_LINES` while compiling, but [`prepare()`](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/src/pystachy_compiler/cached_run.py#L213-L214) keys other settings only, with `os.getenv(k, "")`; [`driver.py`](https://github.com/den-run-ai/pystachy/blob/ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7/src/pystachy_compiler/driver.py#L1060-L1062) rejects the empty value. Prepared with Claude Code assistance.

## Done when

Every compile-affecting setting, including empty values, is keyed or bypasses the cache, so hits reproduce uncached results and errors. `docs/program-cache.md` lists them, and cache tests cover both cases.
````

### 6. Match CPython's input() error for a closed stdin

Labels: `bug`, `priority: P2` · P2 · 102 words

````markdown
## Problem

With standard input closed, `input()` raises `EOFError`. CPython raises `RuntimeError: lost sys.stdin`, so `except EOFError` handlers run where CPython's would not.

## Scope

On main `ce8c887`, run [input_closed.py](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/input_closed.py) with stdin closed (`0<&-`):

```python
try:
    print("got", input())
except EOFError:
    print("EOFError")
except RuntimeError as e:
    print("RuntimeError", e)
```

CPython 3.13.18 prints `RuntimeError lost sys.stdin`; JIT and AOT print `EOFError`. With an empty stdin (`< /dev/null`), all three print `EOFError`. Prepared with Claude Code assistance.

## Done when

`input()` with a closed stdin raises CPython's exception and message in JIT and AOT, or the difference is documented as a deviation with a test.
````

## Comment drafts for existing issues

Comments need no sections. Replace `#A` and `#B` with the numbers of drafts 4 and 2 once they are filed.

### On #1154

````markdown
Rechecked on main `ce8c887` after #1162. Inherited pipes on descriptors 3–10, 63, 64, 200 and 1000 keep their contents on hosted, native (cache on and off), MCJIT, embedding and AOT paths, so the reported overwrite is fixed.

Two gaps remain against "matching CPython/AOT": `lli` launches leak the JIT inputs on the lowest free descriptors (#A), and MCJIT's jitdump file takes closed standard streams (#B). I suggest closing this issue once those are filed, since each has its own acceptance check. [Runner](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/run.py). Prepared with Claude Code assistance.
````

### On #50

````markdown
Still reproduces on main `ce8c887`. When the parent sets SIGINT to `SIG_IGN`, hosted JIT (the PyPI install path), `PYSTACHY_PROGRAM_CACHE=0` and MCJIT runs show SIGINT as caught in `/proc/self/status`, and SIGINT raises `KeyboardInterrupt`. CPython, AOT and cached native runs keep it ignored; default Linux native runs avoid it only because they execute the cached executable. [Check](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/sigint.py) · [runner](https://github.com/den-run-ai/pystachy/blob/8465735d26b6f9c55b63564137237c1585762c9d/research/status-20261108/repro/run.py). Prepared with Claude Code assistance.
````
