# Bootstrap: CPython runs pystachy.py on itself (stage 1); that native compiler rebuilds
# itself (stage 2) and must reproduce its own LLVM IR byte for byte (fixed point).
PY ?= $(shell command -v python3.13 || command -v python3)
export PYSTACHY_LLVM ?= $(shell $(PY) -c 'import pystachy; print(pystachy.llvm_dir())')
COMPILER_SOURCES := pystachy.py $(wildcard src/*.py src/pystachy_compiler/*.py)

pystachy: $(COMPILER_SOURCES) runtime.c runtime.py
	mkdir -p build
	$(PY) pystachy.py build pystachy.py -o build/pystachy1
	build/pystachy1 build pystachy.py -o build/pystachy2
	$(PY) pystachy.py ir pystachy.py -o build/stage1.ll
	build/pystachy1 ir pystachy.py -o build/stage2.ll
	build/pystachy2 ir pystachy.py -o build/stage3.ll
	cmp build/stage1.ll build/stage2.ll && cmp build/stage2.ll build/stage3.ll
	@echo "fixed point: stage1 == stage2 == stage3 ($$(wc -l < build/stage1.ll) lines of IR)"
	$(PY) pystachy.py rt runtime.py -o build/rt1.ll
	build/pystachy1 rt runtime.py -o build/rt2.ll
	build/pystachy2 rt runtime.py -o build/rt3.ll
	cmp build/rt1.ll build/rt2.ll && cmp build/rt2.ll build/rt3.ll
	@echo "fixed point: runtime.py's IR, rt1 == rt2 == rt3 ($$(wc -l < build/rt1.ll) lines)"
	cp build/pystachy2 pystachy

# FILES: only these cases, e.g. make test FILES="tests/str_*.py tests/errors/rtmode_*.py"
test: pystachy
	tests/run.sh ./pystachy "jit aot" $(FILES)

# the CPython-hosted compiler runs as a module, whose bytecode CPython caches (it compiles a script's
# source again at every start); every compiler module is checked by hash, not its mtime
test-py:
	$(PY) -c 'import glob, py_compile as c; [c.compile(p, doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH) for p in ["pystachy.py"] + sorted(glob.glob("src/**/*.py", recursive=True))]'
	tests/run.sh "$(PY) -m pystachy" "jit aot" $(FILES)

# the cached runtime's rules (tests/cache.sh: when it is used, built again, and what it is keyed by),
# with the native compiler, then the CPython-hosted one ($(PY) loads the extension modules)
test-cache: pystachy
	PY="$(PY)" tests/cache.sh ./pystachy
	tests/cache.sh "$(PY) -m pystachy"

# the FFI's tests (docs/ffi.md): C calls, and with $(PY)'s libpython, extension modules
test-ffi: pystachy
	PY="$(PY)" tests/ffi/run.sh ./pystachy "jit aot"

bench: pystachy
	PY="$(PY)" bench/run.sh

# Advisory diagnostics with separate compilation and in-process execution timings.
# Reuse a verified compiler, e.g. BENCH_COMPILER=build/verify/pystachy2, without
# bootstrapping ./pystachy again. The default still builds the normal compiler.
BENCH_COMPILER ?= ./pystachy
BENCH_ARGS ?=
bench-extended: $(BENCH_COMPILER)
	$(PY) tools/bench_extended.py --compiler "$(BENCH_COMPILER)" $(BENCH_ARGS)

# Correctness only: no wall-clock performance thresholds on shared CI runners.
bench-extended-check: $(BENCH_COMPILER)
	$(PY) -m unittest discover -s tools -p test_bench_extended.py
	$(PY) tools/bench_extended.py --compiler "$(BENCH_COMPILER)" --smoke --json build/extended-smoke.json

# Slots that dict lookups visit for keys that defeat a weak hash (tools/dictprobe.c): deterministic
# counts, so the run fails above a fixed limit; the timings it prints are for information only
# (it includes runtime.c, whose hash functions are runtime.py's: llvm-link adds those). It also
# checks that the collector scans no key table of ints, and those of strs and tuples
LLVMBIN = $(if $(PYSTACHY_LLVM),"$(PYSTACHY_LLVM)/")
dictprobe: tools/dictprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/dictprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/dictprobe.c -o build/dictprobe.ll
	$(LLVMBIN)llvm-link build/dictprobe-rt.ll build/dictprobe.ll -o build/dictprobe.bc
	$(LLVMBIN)clang -O2 build/dictprobe.bc -o build/dictprobe -lm
	build/dictprobe
	PYSTACHY_GC_STRESS=1 build/dictprobe --hash-cache

# Empty lists release historical backing; range-list backing is pointer-free and safely mutable.
listprobe: tools/listprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/listprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/listprobe.c -o build/listprobe.ll
	$(LLVMBIN)llvm-link build/listprobe-rt.ll build/listprobe.ll -o build/listprobe.bc
	$(LLVMBIN)clang -O2 build/listprobe.bc -o build/listprobe -lm
	build/listprobe
	PYSTACHY_GC_STRESS=1 build/listprobe

# Shared container DAGs compare without expanding into their logical trees.
eqprobe: tools/eqprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/eqprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/eqprobe.c -o build/eqprobe.ll
	$(LLVMBIN)llvm-link build/eqprobe-rt.ll build/eqprobe.ll -o build/eqprobe.bc
	$(LLVMBIN)clang -O2 build/eqprobe.bc -o build/eqprobe -lm
	build/eqprobe
	PYSTACHY_GC_STRESS=1 build/eqprobe

# Writable files' malloc'd buffers count as heap bytes: dropped files run collections, closes balance.
fileprobe: tools/fileprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/fileprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/fileprobe.c -o build/fileprobe.ll
	$(LLVMBIN)llvm-link build/fileprobe-rt.ll build/fileprobe.ll -o build/fileprobe.bc
	$(LLVMBIN)clang -O2 build/fileprobe.bc -o build/fileprobe -lm
	build/fileprobe
	build/fileprobe --lib
	PYSTACHY_GC_STRESS=1 build/fileprobe

# sum(), min() and max() of generators and range() stream: 10^8 items in 64 MiB (AOT).
streamprobe: pystachy
	$(PY) tools/streamprobe.py

# Inspect the bitcode passed to lli, then run it: dead functions must not reach code generation.
jitprobe: pystachy
	$(PY) tools/jitprobe.py

# Opt-in Unicode porting checks, including cache reuse and GC-stress exception paths.
unicode-audit: pystachy
	$(PY) tools/unicode_audit.py

# Full verification (bootstrap, both compilers, the runtime cache, Python-free stage, UBSan, GC stress, IR check,
# benchmarks, dict probes, scaling) -> build/verification.json
verify:
	PY="$(PY)" tests/verify.sh

# IR oracle for refactors (tools/irsame.sh): ./pystachy must emit what the compiler of commit REF (default
# HEAD) emits -- IR, messages, exit status -- for every corpus program, or for FILES; irsame-py compares the
# CPython-hosted compilers. build/ref holds REF's pystachy.py, src/, runtime.c (with ryu/, which it includes),
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
	tests/run.sh "$(CPYTHON_SUBSET_COMPILER)" "jit aot" tests/upstream_fnmatch.py tests/upstream_textwrap_wrap.py tests/upstream_textwrap_layout.py tests/upstream_textwrap_indent.py tests/upstream_functools_cache.py tests/deviations/upstream_textwrap_unicode.py tests/errors/upstream_textwrap_field_rebind.py

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

# lib/re, run by CPython, must enter its matcher and make contexts no more often than fixed limits
# allow for textwrap's patterns, with CPython's results (tools/re_probe.py: deterministic counts);
# RE_PROBE="--time ./pystachy" also times tools/re_bench.py compiled and under CPython
RE_PROBE ?=
re-probe:
	$(PY) tools/re_probe.py $(RE_PROBE)

# ruff (findings only, ruff.toml), shellcheck of the scripts as POSIX sh, and clang's warnings on the C
# sources; pip install -r tools/requirements-dev.txt gives the versions CI uses
lint:
	ruff check
	shellcheck -s sh -S warning $(wildcard tests/*.sh tests/ffi/*.sh tools/*.sh bench/*.sh)
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror runtime.c tools/dictprobe.c tools/listprobe.c tools/eqprobe.c tools/fileprobe.c pyext.c pyembed.c
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror -DPYX_ABI3T pyext.c

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

.PHONY: test test-py test-cache test-ffi bench bench-extended bench-extended-check dictprobe listprobe eqprobe fileprobe streamprobe jitprobe unicode-audit verify irsame irsame-py ref check-ir check-runtime check-recordings port-check test-cpython-subset port-check-large re-fuzz re-probe lint clean install uninstall test-install
