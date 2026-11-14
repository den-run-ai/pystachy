# Bootstrap: CPython runs pystachy.py on itself (stage 1); that native compiler rebuilds
# itself (stage 2) and must reproduce its own LLVM IR byte for byte (fixed point).
PY ?= $(shell command -v python3.13 || command -v python3)
export PYSTACHY_LLVM ?= $(shell $(PY) -c 'import pystachy; print(pystachy.llvm_dir())')
COMPILER_SOURCES := pystachy.py lib/_pystachy_cache.py $(wildcard src/*.py src/pystachy_compiler/*.py)
# Experimental: lower only the temporary first-stage compiler's AOT tier.
BOOTSTRAP_AOT_OPT ?= 2

pystachy: $(COMPILER_SOURCES) runtime.c runtime.py $(wildcard ryu/*.c ryu/*.h mpz/*.c)
	mkdir -p build
	PYSTACHY_AOT_OPT="$(BOOTSTRAP_AOT_OPT)" $(PY) pystachy.py build pystachy.py -o build/pystachy1 --emit-ir build/stage1.ll
	PYSTACHY_AOT_OPT=2 build/pystachy1 build pystachy.py -o build/pystachy2 --emit-ir build/stage2.ll
	build/pystachy2 ir pystachy.py -o build/stage3.ll
	cmp build/stage1.ll build/stage2.ll && cmp build/stage2.ll build/stage3.ll
	@echo "fixed point: stage1 == stage2 == stage3 ($$(wc -l < build/stage1.ll) lines of IR)"
	$(PY) pystachy.py rt runtime.py -o build/rt1.ll
	build/pystachy1 rt runtime.py -o build/rt2.ll
	build/pystachy2 rt runtime.py -o build/rt3.ll
	cmp build/rt1.ll build/rt2.ll && cmp build/rt2.ll build/rt3.ll
	@echo "fixed point: runtime.py's IR, rt1 == rt2 == rt3 ($$(wc -l < build/rt1.ll) lines)"
	cp build/pystachy2 pystachy

# FILES: only these cases, e.g. make test FILES="tests/programs/strings/str_*.py tests/errors/runtime/rtmode_*.py"
test: pystachy
	tests/run.sh ./pystachy "jit aot" $(FILES)

# the CPython-hosted compiler runs as a module, whose bytecode CPython caches (it compiles a script's
# source again at every start); every compiler module is checked by hash, not its mtime
test-py:
	$(PY) -c 'import glob, py_compile as c; [c.compile(p, doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH) for p in ["pystachy.py"] + sorted(glob.glob("src/**/*.py", recursive=True))]'
	tests/run.sh "$(PY) -m pystachy" "jit aot" $(FILES)

.PHONY: test-pytest-native test-pytest-workloads test-pytest-upstream test-pytest-json-upstream

# Hosted collection/oracle and real native execution; no compiler bootstrap needed.
# CI supplies the verified native compiler for repeated builds; examples still
# exercise the hosted compiler in JIT mode.
PYTEST_NATIVE_COMPILER ?= $(PY) $(CURDIR)/pystachy.py
PYTEST_NATIVE_TEST_JOBS ?= 4
PYTEST_NATIVE_PARTS = pytest-native-examples-jit pytest-native-examples-aot pytest-native-controls pytest-native-upstream
.PHONY: $(PYTEST_NATIVE_PARTS)
test-pytest-native:
	printf '%s\n' tools/test_pytest_native*.py | PYSTACHY_PYTEST_NATIVE_COMPILER="$(PYTEST_NATIVE_COMPILER)" xargs -n 1 -P $(PYTEST_NATIVE_TEST_JOBS) sh -c 'exec $(PY) -m unittest discover -s tools -p "$${1##*/}"' sh
	$(MAKE) -j$(PYTEST_NATIVE_TEST_JOBS) $(PYTEST_NATIVE_PARTS)
# Keep modules above separate: some use the examples' default work directory.
# These four parts have separate work directories and can run together safely.
pytest-native-examples-jit:
	PYTHONPATH="$(CURDIR)/ports" PYSTACHY_PATH="$(CURDIR)/ports" $(PY) tools/pytest_native.py examples/pytest_native --mode jit --compare --json build/pytest-native/examples.json
pytest-native-examples-aot:
	PYTHONPATH="$(CURDIR)/ports" PYSTACHY_PATH="$(CURDIR)/ports" $(PY) tools/pytest_native.py examples/pytest_native --mode aot --compare --compiler "$(PYTEST_NATIVE_COMPILER)" --work-dir build/pytest-native-aot --json build/pytest-native-aot/examples.json
pytest-native-controls:
	$(PY) tools/pytest_native_controls.py --compiler "$(PYTEST_NATIVE_COMPILER)" --json build/pytest-controls.json
pytest-native-upstream:
	$(PY) tools/pytest_native_upstream.py --suite fnmatch --suite textwrap --compiler "$(PYTEST_NATIVE_COMPILER)" --json build/pytest-upstream-bundled.json

# Complete optional upstream qualification uses only explicitly fetched pinned
# sources. The bundled fnmatch/textwrap subset above remains offline in CI.
PYTEST_UPSTREAM_ARGS ?=
test-pytest-upstream:
	$(PY) tools/pytest_native_upstream.py --compiler "$(PYTEST_WORKLOAD_COMPILER)" --json build/pytest-upstream.json $(PYTEST_UPSTREAM_ARGS)

JSON_REPAIR_UPSTREAM ?= build/json-repair-upstream
test-pytest-json-upstream:
	$(PY) tools/pytest_native_json_repair.py --upstream "$(JSON_REPAIR_UPSTREAM)" --compiler "$(PYTEST_WORKLOAD_COMPILER)" --json build/pytest-json-upstream.json

# Independent application/benchmark suites share original pytest assertions.
# CI supplies its already verified compiler; local users can use hosted compilation.
PYTEST_WORKLOAD_COMPILER ?= $(PY) $(CURDIR)/pystachy.py
PYTEST_WORKLOAD_JOBS ?= 4
PYTEST_WORKLOAD_ARGS ?=
test-pytest-workloads:
	$(PY) tools/pytest_native_suites.py --compiler "$(PYTEST_WORKLOAD_COMPILER)" --jobs $(PYTEST_WORKLOAD_JOBS) --json build/pytest-workloads.json $(PYTEST_WORKLOAD_ARGS)

# the statements and branches of the compiler's own source (src/pystachy_compiler/) that the corpus, the
# FFI and runtime-cache suites, the IR checks and the compiler's unit tests run (or FILES of the corpus
# alone), measured in the CPython-hosted compiler as test-py runs it (tools/coverage.sh, .coveragerc):
# report only, in build/coverage/; $(PY) needs coverage.py (tools/requirements-dev.txt)
coverage:
	PY="$(PY)" tools/coverage.sh $(FILES)

# the lines and branches of the native runtime's C code (runtime.c, pyembed.c, pyext.c) that the corpus's
# programs (or FILES) and the FFI suite run, built with clang's source-based coverage
# (tools/runtime_coverage.sh): report only, in build/runtime-coverage/; needs clang's profile runtime
# (Ubuntu's libclang-rt-18-dev, which tools/setup.sh installs)
runtime-coverage: pystachy
	PY="$(PY)" tools/runtime_coverage.sh $(FILES)

# the corpus (or FILES), JIT and AOT, in configurations that verify does not test (tools/variants.sh):
# the IR passes off in a covering array of their pairs (PYSTACHY_OPT), the runtime and AOT programs
# built at -O0 (PYSTACHY_CFLAGS); VARIANTS="opt-1 cflags-O0" selects some; logs in build/variants/
variants: pystachy
	PY="$(PY)" tools/variants.sh $(FILES)

# the cached runtime's rules (tests/cache.sh: when it is used, built again, and what it is keyed by),
# with the native compiler, then the CPython-hosted one ($(PY) loads the extension modules)
test-cache: pystachy
	PY="$(PY)" tests/cache.sh ./pystachy
	tests/cache.sh "$(PY) -m pystachy"

# Linux native program cache: invalidation, effects, lifecycle and skipped work.
PROGRAM_CACHE_COMPILER ?= ./pystachy
test-program-cache: $(PROGRAM_CACHE_COMPILER)
	$(PY) -m unittest discover -s tools -p 'test_program_cache*.py'
	$(PY) -m unittest discover -s tools -p 'test_cached_run*.py'
	$(PY) -m unittest discover -s tools -p test_cache_toolchain.py
	$(PY) tools/program_cache_probe.py --compiler "$(PROGRAM_CACHE_COMPILER)" --llvm "$(PYSTACHY_LLVM)" --output build/program-cache-checks.json

# the FFI's tests (docs/ffi.md): C calls, and with $(PY)'s libpython, CPython embedded and extension modules
test-ffi: pystachy
	PY="$(PY)" tests/ffi/run.sh ./pystachy "jit aot"

bench: pystachy
	PY="$(PY)" bench/run.sh

# Advisory diagnostics with separate compilation and in-process execution timings.
# Reuse a verified compiler, e.g. BENCH_COMPILER=build/verify/pystachy2, without
# bootstrapping ./pystachy again. The default still builds the normal compiler.
BENCH_COMPILER ?= ./pystachy
BENCH_ARGS ?=

# Optional socket/readiness bridge: stdlib oracle, JIT/AOT and program GC stress.
netio-check: $(BENCH_COMPILER)
	$(PY) -m unittest discover -s tools -p 'test_netio*.py'
	$(PY) examples/netio/check.py --compiler "$(BENCH_COMPILER)" --json build/netio-check.json
	$(PY) examples/netio/check_drain.py --compiler "$(BENCH_COMPILER)" --json build/netio-drain-checks.json
	mkdir -p build/netio
	$(CC) -std=c11 -O2 -Wall -Wextra -Werror -Wpedantic examples/netio/netio.c examples/netio/ownership.c -o build/netio/ownership
	build/netio/ownership

# Actual compiler output collection and verified socket consumers; advisory timings.
netio-dogfood-check: $(BENCH_COMPILER)
	$(PY) -m unittest discover -s tools -p 'test_netio*.py'
	$(PY) examples/netio/compiler_dogfood.py --compiler "$(BENCH_COMPILER)" --json build/netio-compiler-dogfood.json
	$(PY) examples/netio/benchmark.py --compiler "$(BENCH_COMPILER)" --smoke --json build/netio-benchmark-smoke.json

bench-netio: $(BENCH_COMPILER)
	$(PY) examples/netio/benchmark.py --compiler "$(BENCH_COMPILER)" $(BENCH_ARGS)

# Tiny fixtures through the real CLIs, plus JSON repair and agent loopback HTTP.
example-cli-check: $(BENCH_COMPILER)
	$(PY) -m unittest discover -s tools -p test_check_example_cli.py
	$(PY) tools/check_example_cli.py --compiler "$(BENCH_COMPILER)" --json build/example-cli-smoke.json

bench-extended: $(BENCH_COMPILER)
	$(PY) tools/bench_extended.py --compiler "$(BENCH_COMPILER)" $(BENCH_ARGS)

# Correctness only: no wall-clock performance thresholds on shared CI runners.
bench-extended-check: $(BENCH_COMPILER)
	$(PY) -m unittest discover -s tools -p test_bench_extended.py
	$(PY) tools/bench_extended.py --compiler "$(BENCH_COMPILER)" --smoke --json build/extended-smoke.json

# Ported pyperformance benchmarks (bench/pyperformance/README.md): CPython, JIT and AOT wall times,
# each run's output compared with CPython's; advisory, no thresholds. The check runs small inputs
# once (correctness only); --census needs the pinned sdist.
bench-pyperformance: $(BENCH_COMPILER)
	$(PY) tools/bench_pyperformance.py --compiler "$(BENCH_COMPILER)" $(BENCH_ARGS)

# The optional cblas_dgemm adapter (examples/ndarray/README.md) and nanoGPT's fused-bias linear:
# correctness only, no timings. Needs an LP64 libblas.so.3 (Ubuntu: libopenblas0-pthread or libblas3;
# LD_LIBRARY_PATH=<its directory> selects one) and, for check_blas.py's reference, NumPy in $(PY). Each
# runs under CPython (tools/rt_cpython's FFI twin), JIT, AOT and with a collection at every allocation.
BLAS_PATH = $(CURDIR)/examples/nanogpt:$(CURDIR)/examples/ndarray
blas-check: $(BENCH_COMPILER)
	$(PY) examples/ndarray/check_blas.py --compiler "$(BENCH_COMPILER)" --stress 1
	mkdir -p build
	PYTHONPATH="$(CURDIR)/tools/rt_cpython:$(BLAS_PATH)" $(PY) examples/nanogpt/blas_parity.py
	PYSTACHY_PATH="$(BLAS_PATH)" $(BENCH_COMPILER) run examples/nanogpt/blas_parity.py
	PYSTACHY_PATH="$(BLAS_PATH)" PYSTACHY_GC_STRESS_PROGRAM=1 $(BENCH_COMPILER) run examples/nanogpt/blas_parity.py
	PYSTACHY_PATH="$(BLAS_PATH)" $(BENCH_COMPILER) build examples/nanogpt/blas_parity.py -o build/blas_parity
	build/blas_parity
	PYSTACHY_GC_STRESS=1 build/blas_parity

bench-pyperformance-check: $(BENCH_COMPILER)
	$(PY) -m unittest discover -s tools -p test_bench_pyperformance.py
	$(PY) tools/bench_pyperformance.py --compiler "$(BENCH_COMPILER)" --smoke --json build/pyperformance-smoke.json
	$(PY) tools/pytest_native_suites.py --group pyperformance --compiler "$(BENCH_COMPILER)" --jobs $(PYTEST_WORKLOAD_JOBS) --json build/pytest-pyperformance.json

# CPython/JIT/AOT checksums for match and equivalent handwritten branches.
# Smoke reports validate execution and contain no performance thresholds.
.PHONY: bench-match-check bench-match
bench-match-check: $(BENCH_COMPILER)
	$(PY) -m unittest discover -s bench/match_dispatch -p test_bench.py
	$(PY) bench/match_dispatch/bench.py --compiler "$(BENCH_COMPILER)" --smoke --json build/match-dispatch-smoke.json

bench-match: $(BENCH_COMPILER)
	$(PY) bench/match_dispatch/bench.py --compiler "$(BENCH_COMPILER)" $(BENCH_ARGS)

# Slots that dict lookups visit for keys that defeat a weak hash (tools/dictprobe.c): deterministic
# counts, so the run fails above a fixed limit; the timings it prints are for information only
# (it includes runtime.c, whose hash functions are runtime.py's: llvm-link adds those). It also
# checks that the collector scans no key table of ints, and those of strs, tuples and objects,
# and that only dfindc, the probe of CPython-hashed (KTAG) tables, tests entries for a key past 64
# bits (kbig's -2**63): not dfinds, the probe of every str key, dfindi, that of native int keys, which
# compares no strs, or dfind's generic one, whose tuple items it compares as dfindc does (keq)
LLVMBIN = $(if $(PYSTACHY_LLVM),"$(PYSTACHY_LLVM)/")
dictprobe: tools/dictprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/dictprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/dictprobe.c -o build/dictprobe.ll
	@if grep -Eq '^define[^@]*@hobj[.(]' build/dictprobe.ll; then echo 'dictprobe: scalar-key hashing must inline hobj' >&2; exit 1; fi
	@if [ "$$(grep -Ec '^define[^@]*@dfind[cis]?\(' build/dictprobe.ll)" != 4 ]; then echo 'dictprobe: build/dictprobe.ll must define dfind, dfindc, dfindi and dfinds' >&2; exit 1; fi
	@if sed -n '/^define[^@]*@dfinds(/,/^}/p' build/dictprobe.ll | grep -q -- '-9223372036854775808'; then echo 'dictprobe: the str-key probe (dfinds) must not test entries for wide int keys' >&2; exit 1; fi
	@if sed -n '/^define[^@]*@dfindi(/,/^}/p' build/dictprobe.ll | grep -Eq '@(bcmp|memcmp|pys_str_eq)\('; then echo 'dictprobe: dfindi, the probe of native int keys, must compare no strs (str keys use dfinds)' >&2; exit 1; fi
	@if sed -n '/^define[^@]*@dfindi(/,/^}/p' build/dictprobe.ll | grep -q -- '-9223372036854775808'; then echo 'dictprobe: dfindi, the probe of native int keys, must not test entries for wide int keys (hbig)' >&2; exit 1; fi
	@ktag=$$(sed -n '/^define[^@]*@dfindc(/,/^}/p' build/dictprobe.ll | grep -c -- '-9223372036854775808'); \
	generic=$$(sed -n '/^define[^@]*@dfind(/,/^}/p' build/dictprobe.ll | grep -c -- '-9223372036854775808'); \
	if [ "$$ktag" -le "$$generic" ]; then echo "dictprobe: dfindc must test entries for wide int keys, and dfind's generic probe must not: they compare $$ktag and $$generic words with -2**63" >&2; exit 1; fi
	$(LLVMBIN)llvm-link build/dictprobe-rt.ll build/dictprobe.ll -o build/dictprobe.bc
	$(LLVMBIN)clang -O2 build/dictprobe.bc -o build/dictprobe -lm
	build/dictprobe
	PYSTACHY_GC_STRESS=1 build/dictprobe --hash-cache

# Empty lists release historical backing; range-list backing is pointer-free and safely mutable;
# dropped pointer-free large arrays that are most of what is allocated run a collection every
# 4 MiB of them; small objects, large arrays among more small objects and arrays of pointers,
# every 32 MiB.
listprobe: tools/listprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/listprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/listprobe.c -o build/listprobe.ll
	$(LLVMBIN)llvm-link build/listprobe-rt.ll build/listprobe.ll -o build/listprobe.bc
	$(LLVMBIN)clang -O2 build/listprobe.bc -o build/listprobe -lm
	build/listprobe
	PYSTACHY_GC_STRESS=1 build/listprobe

# Shared container DAGs compare without expanding into their logical trees; dicts and sets of objects
# compare without hashing them again, and those hashed by identity without the program's __eq__.
eqprobe: tools/eqprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/eqprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/eqprobe.c -o build/eqprobe.ll
	$(LLVMBIN)llvm-link build/eqprobe-rt.ll build/eqprobe.ll -o build/eqprobe.bc
	$(LLVMBIN)clang -O2 build/eqprobe.bc -o build/eqprobe -lm
	build/eqprobe
	PYSTACHY_GC_STRESS=1 build/eqprobe

# Writable files' malloc'd buffers count as heap bytes: dropped files run collections, closes balance.
# Text reads keep their per-byte helpers inline, including the EOF/error retry path.
fileprobe: tools/fileprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/fileprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/fileprobe.c -o build/fileprobe.ll
	@if [ "$$(grep -Ec '^define[^@]*@pys_file_read(line)?\(' build/fileprobe.ll)" != 2 ]; then echo 'fileprobe: IR must define text read and readline' >&2; exit 1; fi
	@if grep -Eq '^define[^@]*@get(nl)?[.(]' build/fileprobe.ll; then echo 'fileprobe: text reads must inline per-byte get/getnl helpers' >&2; exit 1; fi
	$(LLVMBIN)llvm-link build/fileprobe-rt.ll build/fileprobe.ll -o build/fileprobe.bc
	$(LLVMBIN)clang -O2 build/fileprobe.bc -o build/fileprobe -lm
	build/fileprobe
	build/fileprobe --lib
	PYSTACHY_GC_STRESS=1 build/fileprobe

# POSIX select prototype: real pipes, signal interruptions and timeout deadlines.
selectprobe: tools/selectprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/selectprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/selectprobe.c -o build/selectprobe.ll
	$(LLVMBIN)llvm-link build/selectprobe-rt.ll build/selectprobe.ll -o build/selectprobe.bc
	$(LLVMBIN)clang -O2 build/selectprobe.bc -o build/selectprobe -lm
	build/selectprobe
	PYSTACHY_GC_STRESS=1 build/selectprobe

# Real weak references: no strong target edge, cleared before reuse, dead handles pruned.
weakrefprobe: tools/weakrefprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/weakrefprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/weakrefprobe.c -o build/weakrefprobe.ll
	$(LLVMBIN)llvm-link build/weakrefprobe-rt.ll build/weakrefprobe.ll -o build/weakrefprobe.bc
	$(LLVMBIN)clang -O2 build/weakrefprobe.bc -o build/weakrefprobe -lm
	build/weakrefprobe
	PYSTACHY_GC_STRESS=1 build/weakrefprobe

# Any and union boxes take exact 16-byte slots: a pointer to a box's payload keeps it, one past its end does not.
boxprobe: tools/boxprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/boxprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/boxprobe.c -o build/boxprobe.ll
	$(LLVMBIN)llvm-link build/boxprobe-rt.ll build/boxprobe.ll -o build/boxprobe.bc
	$(LLVMBIN)clang -O2 build/boxprobe.bc -o build/boxprobe -lm
	build/boxprobe
	PYSTACHY_GC_STRESS=1 build/boxprobe

# sum(), min() and max() of generators and range() stream: 10^8 items in 64 MiB (AOT).
streamprobe: pystachy
	$(PY) tools/streamprobe.py

# Inspect the bitcode passed to lli, then run it: dead functions must not reach code generation.
jitprobe: pystachy
	$(PY) -m unittest discover -s tools -p test_lljit.py
	$(PY) tools/jitprobe.py
	$(PY) tools/jitfdprobe.py

# AOT drops opt-in runtime code only when neither the program nor an import opts in.
aotprobe: pystachy
	$(PY) tools/aotprobe.py

# Opt-in Unicode porting checks, including cache reuse and GC-stress exception paths.
unicode-audit: pystachy
	$(PY) tools/unicode_audit.py

# Code-point caches survive owned appends and GC; raw-byte joins invalidate unsafe counts.
unicodeprobe: tools/unicodeprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/unicodeprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/unicodeprobe.c -o build/unicodeprobe.ll
	$(LLVMBIN)llvm-link build/unicodeprobe-rt.ll build/unicodeprobe.ll -o build/unicodeprobe.bc
	$(LLVMBIN)clang -O2 build/unicodeprobe.bc -o build/unicodeprobe -lm
	build/unicodeprobe
	PYSTACHY_GC_STRESS=1 build/unicodeprobe

# Bounded word scanning agrees with a scalar oracle and never crosses guard pages.
bytescanprobe: tools/bytescanprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/bytescanprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/bytescanprobe.c -o build/bytescanprobe.ll
	$(LLVMBIN)llvm-link build/bytescanprobe-rt.ll build/bytescanprobe.ll -o build/bytescanprobe.bc
	$(LLVMBIN)clang -O2 build/bytescanprobe.bc -o build/bytescanprobe -lm
	build/bytescanprobe
	PYSTACHY_GC_STRESS=1 build/bytescanprobe

# Float conversion retains terminator bounds and avoids suitable ASCII temporaries.
floatprobe: tools/floatprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/floatprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/floatprobe.c -o build/floatprobe.ll
	$(LLVMBIN)llvm-link build/floatprobe-rt.ll build/floatprobe.ll -o build/floatprobe.bc
	$(LLVMBIN)clang -O2 build/floatprobe.bc -o build/floatprobe -lm
	build/floatprobe
	PYSTACHY_GC_STRESS=1 build/floatprobe

# Full verification (bootstrap, both compilers, the runtime cache, Python-free stage, UBSan, GC stress, IR check,
# benchmarks, dict probes, scaling) -> build/verification.json
verify:
	PY="$(PY)" tests/verify.sh

# IR oracle for refactors (tools/irsame.sh): ./pystachy must emit what the compiler of commit REF (default
# HEAD) emits -- IR, messages, exit status -- for every corpus program, or for FILES; irsame-py compares the
# CPython-hosted compilers. build/ref holds REF's pystachy.py, src/, runtime.c (with ryu/ and mpz/, which it includes),
# lib/ and stage-2 compiler, built as above and rebuilt only for another commit; each compiler uses the
# runtime.c and lib/ beside it.
REF ?= HEAD
irsame: pystachy ref
	PYSTACHY_HOME= tools/irsame.sh build/ref/pystachy ./pystachy $(FILES)

irsame-py: ref
	PYSTACHY_HOME= tools/irsame.sh "$(PY) build/ref/pystachy.py" "$(PY) pystachy.py" $(FILES)

ref:
	@c=$$(git rev-parse --verify --quiet '$(REF)^{commit}') || { echo "REF=$(REF) is not a commit"; exit 1; }; \
	if [ -x build/ref/pystachy ] && [ "$$(cat build/ref/commit 2> /dev/null)" = $$c ]; then \
	  echo "build/ref: the compiler of $(REF) ($$c)"; \
	else \
	  echo "build/ref: building the compiler of $(REF) ($$c)"; \
	  rm -rf build/ref && mkdir -p build/ref && \
	  git show $$c:pystachy.py > build/ref/pystachy.py && git show $$c:runtime.c > build/ref/runtime.c && \
	  { ! git cat-file -e $$c:src 2> /dev/null || git archive $$c src | tar -xf - -C build/ref; } && \
	  { ! git cat-file -e $$c:runtime.py 2> /dev/null || git show $$c:runtime.py > build/ref/runtime.py; } && \
	  { ! git cat-file -e $$c:lib 2> /dev/null || git archive $$c lib | tar -xf - -C build/ref; } && \
	  { ! git cat-file -e $$c:ryu 2> /dev/null || git archive $$c ryu | tar -xf - -C build/ref; } && \
	  { ! git cat-file -e $$c:mpz 2> /dev/null || git archive $$c mpz | tar -xf - -C build/ref; } && \
	  PYSTACHY_HOME= $(PY) build/ref/pystachy.py build build/ref/pystachy.py -o build/ref/pystachy1 && \
	  PYSTACHY_HOME= build/ref/pystachy1 build build/ref/pystachy.py -o build/ref/pystachy && \
	  echo $$c > build/ref/commit; \
	fi

# the IR check (PYSTACHY_IRCHECK=1) and llvm-as must accept the IR of every corpus program that compiles,
# and of runtime.py, or of FILES (tools/check_ir.sh)
check-ir: pystachy
	tools/check_ir.sh ./pystachy $(FILES)

# the compiler's RUNTIME table must agree with runtime.c and runtime.py, and no function of runtime.py
# may reach itself through runtime.c (tools/check_runtime.py)
check-runtime:
	$(PY) tools/check_runtime.py

# every recording of a differential test must be what CPython (of .python-version) prints, every
# deviation still deviate, lib/'s copies be CPython's files, and no *.rej, *.orig or core file lie in
# the tree (tests/record.sh --check; CI's Lint workflow runs it)
check-recordings:
	PYTHON="$(PY)" tests/record.sh --check
	$(PY) tools/check_agent_source.py

# Prototype port acceptance: pinned upstream inputs, reviewed adaptations, case inventory,
# and the unedited upstream suites on CPython against the edited fnmatch/textwrap modules.
port-check:
	$(PY) -m unittest discover -s tools -p test_port_check.py
	$(PY) tools/port_check.py --json build/port-check.json

# Supported methods from CPython's actual test_fnmatch, test_textwrap and test_functools.
# These files also belong to the normal corpus, so every existing CI configuration runs them.
CPYTHON_SUBSET_COMPILER ?= ./pystachy
test-cpython-subset: $(CPYTHON_SUBSET_COMPILER)
	tests/run.sh "$(CPYTHON_SUBSET_COMPILER)" "jit aot" tests/programs/upstream/upstream_fnmatch.py tests/programs/upstream/upstream_textwrap_wrap.py tests/programs/upstream/upstream_textwrap_layout.py tests/programs/upstream/upstream_textwrap_indent.py tests/programs/upstream/upstream_functools_cache.py tests/programs/upstream/upstream_textwrap_unicode.py tests/programs/upstream/upstream_textwrap_field_rebind.py

# Large upstream regex cases with normal GC, outside the collect-at-every-allocation corpus.
# Reuse a verified compiler by setting PORT_COMPILER; the default bootstraps one.
PORT_COMPILER ?= ./pystachy
port-check-large: $(PORT_COMPILER)
	$(PY) tools/re_upstream_large.py $(if $(PYSTACHY_LLVM),--llvm "$(PYSTACHY_LLVM)") "$(PORT_COMPILER)"

# lib/re, run by CPython, must compile random patterns to CPython's code and errors and match, split
# and substitute as CPython's re, also on Pystachy's UTF-8 strs, and so must test_re's largest cases
# (tools/re_fuzz.py; deterministic: N=2000 patterns, SEED=1, e.g. make re-fuzz RE_FUZZ="20000 7")
RE_FUZZ ?=
re-fuzz:
	$(PY) tools/re_fuzz.py $(RE_FUZZ)

# dynamic Any: seeded programs that apply operators, comparisons and builtins to Any values must
# print what CPython prints, but for the documented deviations, and keep its identity and
# containment invariants and strict typed/Any parity (tools/dynany_fuzz.py, #802; default:
# 3 programs of 150 random + 30 parity cases, JIT; verify also runs AOT and program GC stress).
# e.g. make dynany-fuzz DYNANY_FUZZ="--aot --gc-stress 10 300"
DYNANY_FUZZ ?=
dynany-fuzz: pystachy
	$(PY) tools/dynany_fuzz.py $(DYNANY_FUZZ)

# Enable dynamic Any across the program corpus, with a fresh CPython oracle and JIT/AOT.
DYNANY_OPTIN ?=
dynany-optin: pystachy
	$(PY) tools/dynany_optin.py --compiler ./pystachy --modes jit aot --report build/dynany-optin.json $(DYNANY_OPTIN)

# Opt the program corpus in to promoting ints the same way (tools/python_int_optin.py): a report of
# every check, which PYTHON_INT_OPTIN="--compare BASE" compares with an earlier one, BASE, failing
# where a check that passes there fails now (docs/testing.md)
PYTHON_INT_OPTIN ?=
python-int-optin: pystachy
	$(PY) tools/python_int_optin.py --compiler ./pystachy --modes jit aot --report build/python-int-optin.json $(PYTHON_INT_OPTIN)

# Enforce the reviewed promoting-int compatibility baseline, including every case and both modes.
PYTHON_INT_GATE ?=
python-int-gate: pystachy
	$(PY) tools/python_int_gate.py --compiler ./pystachy --modes jit aot --report build/python-int-gate.json $(PYTHON_INT_GATE)

# lib/re, run by CPython, must enter its matcher and make contexts no more often than fixed limits
# allow for textwrap's patterns, with CPython's results (tools/re_probe.py: deterministic counts);
# RE_PROBE="--time ./pystachy" also times tools/re_bench.py compiled and under CPython
RE_PROBE ?=
re-probe:
	$(PY) tools/re_probe.py $(RE_PROBE)

# matchers that tools/re_specialize.py generates for random patterns, run by lib/re on CPython, must
# match as CPython's re does (deterministic: N=400 patterns, SEED=1, e.g. make re-specialize-check
# RE_SPECIALIZE="4000 7"; tools/test_re_specialize.py, which Lint runs, checks 300)
RE_SPECIALIZE ?=
re-specialize-check:
	$(PY) tools/re_specialize.py check $(RE_SPECIALIZE)

# Hosted checks use the pinned development tools; no LLVM or bootstrap needed.
typecheck:
	@command -v mypy >/dev/null || { echo "mypy is required: install tools/requirements-dev.txt and activate its environment" >&2; exit 1; }
	mypy --config-file mypy.ini

lint-python:
	@command -v ruff >/dev/null || { echo "ruff is required: install tools/requirements-dev.txt and activate its environment" >&2; exit 1; }
	ruff check
	ruff check --no-force-exclude bench/pyperformance/pytest/*.py

# Fast feedback for compiler edits; full native/runtime validation remains in verify.
check-fast: lint-python typecheck check-repository
	$(PY) -m unittest discover -s tools -p test_function_summaries.py
	$(PY) -m unittest discover -s tools -p 'test_typed*.py'
	$(PY) -m unittest discover -s tools -p 'test_json*.py'
	$(PY) -m unittest discover -s tools -p test_numeric_identity.py
	$(PY) -m unittest discover -s tools -p test_identity_scope.py
	$(PY) -m unittest discover -s tools -p test_toml_boundary.py
	$(PY) -m unittest discover -s tools -p test_dynamic_any_inventory.py
	$(PY) -m unittest discover -s tools -p test_dynany_comparisons.py
	$(PY) -m unittest discover -s tools -p test_dynany_dict_kinds.py
	$(PY) -m unittest discover -s tools -p test_diagnostic_capture.py
	$(PY) -m unittest discover -s tools -p test_loader_preprocessing.py
	$(PY) -m unittest discover -s tools -p test_ctypes_schema.py
	$(PY) -m unittest discover -s tools -p test_ffi_twin.py
	$(PY) -m unittest discover -s tools -p test_parser_allocations.py
	$(PY) -m unittest discover -s tools -p test_exception_bindings.py
	$(PY) -m unittest discover -s tools -p test_inspect_compiler.py
	$(PY) -m unittest discover -s tools -p 'test_lean_boundary*.py'
	$(PY) -m unittest discover -s tools -p test_lean_access.py
	$(PY) -m unittest discover -s tools -p test_lean_inline.py
	$(PY) -m unittest discover -s tools -p test_lean_effects.py
	$(PY) -m unittest discover -s tools -p test_lean_closure_cells.py
	$(PY) -m unittest discover -s tools -p test_lean_range_bounds.py
	$(PY) -m unittest discover -s tools -p 'test_lean_guard*.py'
	$(PY) -m unittest discover -s tools -p test_lean_null_access.py
	$(PY) -m unittest discover -s tools -p test_lean_union_effects.py
	$(PY) -m unittest discover -s tools -p test_lean_union_split.py
	$(PY) -m unittest discover -s tools -p test_lean_union_memory.py
	$(PY) -m unittest discover -s tools -p test_lean_gc.py
	$(PY) -m unittest discover -s tools -p test_lean_generators.py
	$(PY) -m unittest discover -s tools -p test_lean_report.py
	$(PY) -m unittest discover -s tools -p test_lean_fields.py
	$(PY) -m unittest discover -s tools -p test_lean_int.py
	$(PY) -m unittest discover -s tools -p 'test_lean_storage*.py'
	$(PY) -m unittest discover -s tools -p test_lean_layout_metadata.py
	$(PY) -m unittest discover -s tools -p test_source_lines.py
	$(PY) -m unittest discover -s tools -p test_pystachy_toolchain.py
	$(PY) -m unittest discover -s tools -p test_retained_ir.py
	$(PY) -m unittest discover -s tools -p test_compiler_pgo.py
	$(PY) -m unittest discover -s tools -p test_jitfdprobe.py

# Optional development dependency, pinned by tools/lean_boundary/lean-toolchain.
# The ordinary compiler and runtime do not invoke Lean.
check-lean-boundary:
	cd tools/lean_boundary && lake build
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p 'test_lean_boundary*.py'
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_access.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_inline.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_effects.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_closure_cells.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_range_bounds.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p 'test_lean_guard*.py'
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_null_access.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_union_effects.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_union_split.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_union_memory.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_gc.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_generators.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_fields.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_int.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p 'test_lean_storage*.py'
	$(PY) -m unittest discover -s tools -p test_lean_layout_metadata.py

# Every dyn.payload read of the dynamic-Any test programs, each compiled by the hosted
# compiler, proved guarded by the Lean checker (tools/lean_boundary/README.md), and every
# unchecked list read and dict entry proved in bounds and live (tools/lean_boundary/ACCESS.md).
LEAN_CORPUS_FLAGS ?=
check-lean-corpus:
	cd tools/lean_boundary && lake build
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_corpus.py
	$(PY) tools/check_lean_corpus.py $(LEAN_CORPUS_FLAGS)

# Every promoting-int fit claim (a null digit pointer selected after pys_big_op) of the test
# programs that opt in to promoting ints, proved by the Lean checker (tools/lean_boundary/INT.md).
LEAN_INT_FLAGS ?=
check-lean-int:
	cd tools/lean_boundary && lake build
	$(PY) tools/check_lean_int.py --corpus $(LEAN_INT_FLAGS)

# Low words, tuple digit slots and representation crossings, including imported int mode.
LEAN_STORAGE_FLAGS ?=
check-lean-storage:
	cd tools/lean_boundary && lake build
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p 'test_lean_storage*.py'
	$(PY) tools/check_lean_storage_corpus.py $(LEAN_STORAGE_FLAGS)

.PHONY: check-lean-storage

# Every Lean check over every differential test program and deviation, each compiled once, into
# the small committed report tools/lean_boundary/REPORT.md (tools/lean_report.py). Run it after
# a change to typed IR, a pass a check covers or a checker; --status says what changed since.
LEAN_REPORT_FLAGS ?=
lean-report:
	cd tools/lean_boundary && lake build
	$(PY) tools/lean_report.py $(LEAN_REPORT_FLAGS)

.PHONY: lean-report

check-repository:
	$(PY) tools/check_repository_hygiene.py
	$(PY) -m unittest discover -s tools -p test_repository_hygiene.py

# ruff (findings only, ruff.toml), shellcheck of the scripts as POSIX sh, and clang's warnings on the C
# sources; pip install -r tools/requirements-dev.txt gives the versions CI uses
lint: lint-python
	$(PY) tools/runtime_roots.py
	shellcheck -s sh -S warning $(wildcard tests/*.sh tests/ffi/*.sh tools/*.sh bench/*.sh)
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror runtime.c tools/dictprobe.c tools/listprobe.c tools/eqprobe.c tools/fileprobe.c tools/selectprobe.c tools/weakrefprobe.c tools/boxprobe.c tools/unicodeprobe.c tools/bytescanprobe.c tools/floatprobe.c pyext.c pyembed.c
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror -DPYX_ABI3T pyext.c
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror -std=c11 -D_GNU_SOURCE -DLLVM_VERSION_MAJOR=18 lljit.c
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror -std=c11 -D_GNU_SOURCE -DLLVM_VERSION_MAJOR=21 lljit.c

clean:
	rm -rf build pystachy

# Native compiler plus its runtime/library resources; no Python needed after installation.
prefix ?= $(HOME)/.local
install: pystachy
	$(PY) tools/install.py --prefix "$(prefix)" $(if $(DESTDIR),--destdir "$(DESTDIR)")

uninstall:
	$(PY) tools/install.py --prefix "$(prefix)" $(if $(DESTDIR),--destdir "$(DESTDIR)") --uninstall

test-install:
	$(PY) -m unittest discover -s tools -p test_install.py

.PHONY: test test-py coverage runtime-coverage variants test-cache test-program-cache test-ffi bench bench-extended bench-extended-check example-cli-check netio-check netio-dogfood-check bench-netio blas-check bench-pyperformance bench-pyperformance-check dictprobe listprobe eqprobe fileprobe selectprobe weakrefprobe boxprobe streamprobe jitprobe aotprobe unicode-audit unicodeprobe bytescanprobe floatprobe verify irsame irsame-py ref check-ir check-runtime check-recordings port-check test-cpython-subset port-check-large re-fuzz dynany-fuzz dynany-optin python-int-optin python-int-gate re-probe re-specialize-check typecheck lint-python check-repository check-fast check-lean-boundary check-lean-corpus check-lean-int lint clean install uninstall test-install

# Explicit programs give a bounded gate; without them this inventories the entire corpus.
LEAN_GUARD_FLAGS ?=
check-lean-guards:
	cd tools/lean_boundary && lake build
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p 'test_lean_guard*.py'
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_null_access.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_union_effects.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_union_split.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_union_memory.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_gc.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_generators.py
	LEAN_BOUNDARY_REQUIRED=1 $(PY) -m unittest discover -s tools -p test_lean_fields.py
	$(PY) tools/check_lean_guard_corpus.py $(LEAN_GUARD_FLAGS)

.PHONY: check-lean-guards
