# Integer promotion handoff

As of 2026-10-26. This file sits under `research/` on branch `claude/integer-promotion-roadmap-9ekvhv`, one commit on top of main `9b39164`. `make check-repository` rejects `research/`, so it cannot be merged by accident; restart the branch from main before new work (`git checkout -B claude/integer-promotion-roadmap-9ekvhv origin/main`).

Steps 1–3 of roadmap #907 are on main at `9b39164`, with parts of steps 4 and 5. Nothing is in flight: no open PR on the branch, no PR watches, no scheduled check-ins. Step 6, big ints in containers, is next once the maintainer says go.

## Roadmap state

Steps 1–3 are done; 4 and 5 are partly done; 6–8 have not started. The plan checkboxes in #907's body are still unticked.

| Step (#907) | Done on main | Left |
| --- | --- | --- |
| 1. Land #906 and `bench/integers` | #910 (with #906's commits), #912 | – |
| 2. Scalar representation | `{i64, ptr}`, decided in #907's comment of 2026-10-26 | – |
| 3. Compiler-level int behind `# pystachy: python-int`, with range proofs | #914; inline paths and proven-fit results in #915 | – |
| 4. Numeric tower | Correctly rounded `float()` and exact int/float comparisons (#914), true division (#916), adapted `test_int` cases (#917); probed operations with the big operand on the right match CPython | Negative powers: `2 ** -1` raises `ValueError` in every module, where CPython gives `0.5`. More pinned `test_long`, `test_float`, `test_bool` cases |
| 5. Protocols and builtins | Format specs and `%` formatting, `bin`/`hex`/`oct`, `bit_length`/`bit_count`, `pow(x, y, m)`, `sum()` (#917) | `__index__`/`__int__` (#322, #510), `int.to_bytes`/`int.from_bytes`, `sys.set_int_max_str_digits`, `range` with big bounds |
| 6. Storage, identity, dispatch | Module variables and closure cells already promote (#914) | Containers, tuples, unions, generator channels, Dynamic `Any` boxes, mixed numeric dict and set keys (#752), `is` |
| 7. Stdlib and native boundaries | `hash()` is CPython's (modulus 2\*\*61 − 1, #914) | `json`, `struct`, `math`, `random`, FFI and extension conversions |
| 8. Gates and default switch | – | Pinned CPython-suite manifest, cost budget, int64 opt-out |

## Merged PRs

All six merged on 2026-10-26 with merge commits, all CI checks green. Each PR body has its validation, measurements and risks.

| PR | Merged as | What it added | Codex |
| --- | --- | --- | --- |
| #917 | `9b39164` | `bit_length()`, `bit_count()`, `bin`/`hex`/`oct`, format specs and `%` formatting, `pow(x, y, m)`, `sum()` past 64 bits, `min`/`max` of big items; #901's `python_int_cpython_int.py` and `python_int_reflection.py` | No findings |
| #916 | `a6098e3` | True division past 64 bits, CPython's `long_true_divide` rounding (listed in `THIRD_PARTY_NOTICES`) | No findings |
| #915 | `bec82db` | Inline `//`, `%`, `<<`, `>>`; proven-fit results; stack temporaries (`MpzTmp`) for 64-bit operands; `MemoryError` for huge shifts | Never finished |
| #914 | `ed0fa8e` | The promoting int behind `# pystachy: python-int`: IR type `int+`, runtime `pys_big_*`, roots, docs | Never finished |
| #912 | `5d8ac54` | `bench/integers`: ten workloads with `mpz` and int64 variants, `run.py`, peak RSS via a C launcher | One finding (RSS), fixed |
| #910 | `a4b2b7d` | #906's masked arithmetic plus a shift-count fix | No findings |

Codex's reviews of #914 and #915 stayed "running" for over an hour and never reported. Those two merged on green CI without a completed independent review.

## Waiting on the maintainer

Two questions were asked and not yet answered. Take no outward action on #901 until the maintainer answers.

- [ ] **#901** (draft prototype, branch `prototype/cpython-int-promotion`): close it with a comment mapping each piece to where it went, or keep it open as a draft reference. Two of its eleven tests are on main (#917). Five need big values in containers or unions (step 6), two need `is` between ints, and two expect runtime `TypeError`s where Pystachy rejects the program at compile time. Its one open Codex finding (`range(3, None)` in `lib/_pystachy_int.py`) belongs to its wrapper class, which main does not use.
- [ ] **Step 6:** start it now, or wait.
- [ ] Tick steps 1–3 in #907's plan, if the maintainer wants the checkboxes kept current.

## Design in force

Every change so far kept #409's ground rule: modules without the comment compile to the same IR, checked with the IR oracle on each PR.

1. **Representation (decision 1).** A promoting int is the IR type `int+`, an LLVM `{i64, ptr}`. A null pointer means the value is the `i64`; otherwise the `i64` is 0 and the pointer is an immutable `Mpz` (30-bit digits, the `mpz` core). Every result that fits is demoted, so two values that fit are equal exactly when their `i64` words are.
2. **Storage (decision 2).** Containers, tuples, unions (also `int | None`), generator channels, `int` parameters of modules that do not opt in, and Dynamic `Any` keep 64-bit ints. A value past 64 bits raises `OverflowError: Python int too large to convert to C long` there. Inside a container or union annotation, `int` is the 64-bit type.
3. **Opt-in (decision 3).** Per module, by a leading `# pystachy: python-int` comment. The compiler, `runtime.py` and `lib/` do not opt in, so self-compilation is unchanged.
4. **Identity (decision 4).** `is` between ints is rejected at compile time in a module that opts in; `x is None` on an int is folded. A module cannot opt in to both promoting ints and Dynamic `Any` yet.

## Gaps against CPython on main

Each snippet below fails in a module that opts in, probed against CPython 3.13.16 with a build of #917's code. Reflected operations (`3 - big`, `1.5 * big`, `7 // big`, `-big % 5`) and `hash()` of big values already match.

| Snippet | CPython 3.13.16 | Pystachy | Step |
| --- | --- | --- | --- |
| `2 ** -1` | `0.5` | `ValueError: negative exponent for int ** int`, in every module | 4 |
| `round(2 ** 70, -3)` | `1180591620717411303000` | `OverflowError` | 4 |
| `(2 ** 70).to_bytes(10, "big")`, `int.from_bytes(b"\x01" * 12, "big")` | bytes, an int | Compile error: no such method | 5 |
| `int(C())`, where `C.__index__` returns `2 ** 70` | `1180591620717411303424` | Compile error: `int()` argument must be a string, bytes or number | 5 |
| `sys.set_int_max_str_digits(5000)` | Sets the limit | Compile error: unsupported call | 5 |
| `range(2 ** 70)` | A range (only its `len()` overflows) | `OverflowError` at `range()` | 5 |
| `divmod(2 ** 70, 7)` | `(168655945816773043346, 2)` | `OverflowError` | 5–6 |
| `[2 ** 70]`, `{2 ** 70: 1}`, `(2 ** 70, 1)`, a yield or an `int \| None` of a big value | Works | `OverflowError` | 6 |
| `math.isqrt(2 ** 70)`, `math.gcd(2 ** 70, 6)` | `34359738368`, `2` | `OverflowError` | 7 |
| `(2 ** 70).__abs__()` | The value | Compile error: no method `__abs__` | – |

## Starting step 6

The target is `bench/integers`'s `containers` workload, which still raises `OverflowError` with `--python-int`. #912 measured CPython at 0.536 s and the explicit `mpz` variant at 0.628 s on it.

- **Where values narrow today.** `gen_big_narrow` in `src/pystachy_compiler/bigints.py` turns an `int+` into a 64-bit int or raises `NARROW`'s message. `conversions.py` calls it at every 64-bit slot and coercion (lines 32, 67 and 145 at `9b39164`); `builtins.py` calls it at four more places and `bigints.py` at two, nine calls in all.
- **The cost to beat.** Decision 2's proxy measured list reads at 1.6–1.8× checked int64 for every scalar design, and 1.14× with two-version loops (#907's step-2 comment). #907 suggests raw int64 items behind an "all small" flag, as PyPy's list strategies keep them, weighed against two-version loops.
- **Collector.** Int lists are pointer-free today: the compiler makes `list[int]`, `list[float]` and `list[bool]` with `pys_list_new_atomic` (`runtime.c`). Items that can hold an `Mpz` pointer must be scanned, and AGENTS.md (#603) asks to mark storage pointer-free only once its representation is proven. Test copy, growth, clear and refill under `PYSTACHY_GC_STRESS_PROGRAM=1` and with `listprobe`/`dictprobe`.
- **Tests to port.** #901's `python_int_cpython_long.py`, `python_int_forward_ref.py`, `python_int_import.py`, `python_int_recursion.py` and `python_int_storage.py` on branch `prototype/cpython-int-promotion` first fail at container or union storage. Main already has a different `python_int_storage.py`, so rename on porting, and record again with `PYTHON=python3.13 tests/record.sh`.
- **The rest of step 6.** `is` (CPython caches −5..256; #901 raised `NotImplementedError` where the answer is ambiguous; decision 4 rejects it at compile time for now), Dynamic `Any` boxes (#780, #858), and mixed numeric dict and set keys (#752).
- **An untraced lead.** `collatz` ran faster with promoting ints than its checked-int64 build (0.033 s against 0.045 s in every sample). Checked int64's lowering may be leaving speed behind.

## Where the code lives

All promoting-int code generation is in `bigints.py`; `docs/python-int.md` is the user-facing guide.

| Path | Role |
| --- | --- |
| `src/pystachy_compiler/bigints.py` | `gen_int_policy` (the opt-in), `gen_to_big`, `gen_big_fits`, `gen_big_arith` (inline paths, then `pys_big_op`), `gen_big_known` (proven-fit results), `gen_big_truediv`, `gen_big_narrow`, `gen_big_builtin`, `gen_big_method`; `BIGOPS` holds `pys_big_op`'s operation codes |
| `src/pystachy_compiler/gen.py` | The `big_*` forwarding methods (the `gen_*` boundary in `src/README.md`) |
| `src/pystachy_compiler/builtins.py` | The builtin hook for promoting ints; `sum()`, `min()`, `max()` through `gen_stream_start`, `gen_reduce`, `gen_reduce_item` |
| `src/pystachy_compiler/conversions.py` | Narrowing into 64-bit slots and coercions |
| `src/pystachy_compiler/expressions.py`, `containers.py` | `%` and `format()` of promoting ints; their `repr()` |
| `src/pystachy_compiler/specs.py` | `BIG = "int+"`; the `big.*` `RUNTIME` entries, whose effects (`R` raises, `A` allocates, `rL` reads lists) `tools/check_runtime.py` checks against `runtime.c` |
| `src/pystachy_compiler/variables.py`, `diagnostics.py` | Module variables' `Mpz` word as a collector root; `INTFILES`, the files that opted in |
| `runtime.c` | `pys_big_*` (op, cmp, cmp_float, str, from_str, from_float, hash, float, truediv, bit_length, bit_count, format, powmod, sum); `big_mpz` with `MpzTmp` stack temporaries |
| `runtime.py` | `fmt()`'s kind 4 and `pys_format_bigdigits`: int formatting from a big value's digits |
| `mpz/mpz.c`, `mpz/README.md` | The `Mpz` core: MicroPython-derived, with CPython's algorithms |
| `tests/programs/numbers/python_int_*.py` | 13 differential programs; helper modules in `tests/python_int_modules/`, reached through `.path` files |
| `tests/deviations/python_int_limits.py`, `tests/errors/numbers/python_int_{dynamic_any,is}.py` | The 64-bit boundaries and the two rejections |
| `tests/upstream/python-int.md`, `tools/test_compiler_state_files.py` | Provenance of the adapted `test_int` cases; the opt-in across imports and restarts |
| `tools/dynany_optin_exceptions.json` | Two entries (JIT, AOT) per python-int program: the Dynamic `Any` replay expects their opt-in conflict |
| `bench/integers/` | The ten workloads, `run.py`, and `results/*.json` (three python-int files so far) |
| `THIRD_PARTY_NOTICES`, `ports/THIRD_PARTY_NOTICES` | Must stay identical; they list the parts derived from CPython's `longobject.c` |

## Validating a change

The PRs ran these steps in this order, as far as each change needed; times are from the shared 4-vCPU VM. CI's full matrix then covers UBSan, `check-ir` and the unit tests.

1. Build: `make PY=<venv>/bin/python3`, with the venv from `tools/requirements-dev.txt` first on `PATH`. About 5 minutes; it checks the three-stage fixed point.
2. Focused tests, about 15 seconds: `tests/run.sh ./pystachy "jit aot" tests/programs/numbers/python_int_*.py tests/errors/numbers/python_int_*.py tests/deviations/python_int_*.py`. Files are positional: `tests/run.sh` ignores `FILES`, which only `make test` reads.
3. The same with `PYSTACHY_GC_STRESS_PROGRAM=1`, then with `PYSTACHY_OPT=-all`.
4. New cases: `PYTHON=python3.13 tests/record.sh NAME`, never Pystachy's output.
5. IR oracle, 6–10 minutes: save main's `./pystachy` first, then `PYSTACHY_HOME=$PWD PYSTACHY_JOBS=4 tools/irsame.sh <main's binary> ./pystachy`. Only programs that opt in may differ; run it on single files to name them.
6. `make PY=<venv>/bin/python3 lint check-runtime check-recordings check-repository`, about 2 minutes.
7. Each new opt-in program needs a JIT and an AOT entry in `tools/dynany_optin_exceptions.json`. Check them with `PYTHON=python3.13 python3 tools/dynany_optin.py --compiler ./pystachy --jobs 4 --report <out>.json --cases <files>`: expected failures only.
8. A change to `runtime.py`'s formatting: also run `tests/programs/strings` and the format-named cases (#917 ran 242 cases).
9. Speed, about 6 minutes: `python3.13 bench/integers/run.py --compiler ./pystachy --cpython python3.13 --samples 5 --cpu 3 --python-int --json <out>.json --only lcg32 collatz cross64 arith128 factorial fibadd bigmul dectext modpow`. Leave out `containers` until step 6. Keep results in `bench/integers/results/` and update `docs/python-int.md`'s table.
10. Push to the session's branch, open a draft PR, then mark it ready, which starts Codex. Wait for all 38 checks (15–20 minutes) and merge with a merge commit and the expected head SHA.

## Pitfalls met in these sessions

Most cost a CI cycle or a rewrite; each has a fix that worked.

- **One branch, one PR.** The session may push only `claude/integer-promotion-roadmap-9ekvhv`. After each merge, run `git checkout -B <branch> origin/main`, cherry-pick the next validated commits and push. A push while CI runs queues the new CI and Lint runs behind the old ones.
- **Stop hook.** It requires the branch pushed. After the last merge, fast-forward the branch to main and push it.
- **Connector footer.** Creating a PR or comment through the GitHub connector appended a "Generated by Claude Code" footer. AGENTS.md forbids it, so update the text again without it and read it back.
- **Hung Codex reviews.** A finished review took 1–5 minutes; #914's and #915's never finished. Don't hold a green PR for one, and say so in the PR body.
- **CPython-derived code.** #916's true division follows `long_true_divide`, so it is listed in both `THIRD_PARTY_NOTICES` copies (they must stay identical) and noted at the function.
- **Strict aliasing.** A stack `Mpz` must be the `MpzTmp` union, not a cast `uint64_t` array.
- **Runtime effects.** A new runtime function's `specs.py` effects must match what it does: `pys_big_sum` needed `rL`, or `check-runtime` fails.
- **Recording.** CPython really runs each case: `sum(range(10**10))` never finished. Wrap output that can hold a NUL byte (format `c` of 0) in `ascii()`.
- **Results files.** A second benchmark run on the same day needs its own file name, so earlier PRs' citations stay valid.
- **Scratch state.** Worktrees, builds and scripts lived in the session's scratchpad and are gone. Everything of value is merged or in a PR body; #916's body has the randomized true-division check.
