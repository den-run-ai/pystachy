# Bootstrap: CPython runs pystachy.py on itself (stage 1); that native compiler rebuilds
# itself (stage 2) and must reproduce its own LLVM IR byte for byte (fixed point).
PY ?= python3

pystachy: pystachy.py runtime.c runtime.py
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
# 16k lines again at every start); the cache is checked against pystachy.py's hash, not its mtime
test-py:
	$(PY) -c 'import py_compile as c; c.compile("pystachy.py", doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH)'
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
BENCH_ARGS ?=
bench-extended: pystachy
	$(PY) tools/bench_extended.py $(BENCH_ARGS)

# Correctness only: no wall-clock performance thresholds on shared CI runners.
bench-extended-check: pystachy
	$(PY) -m unittest discover -s tools -p test_bench_extended.py
	$(PY) tools/bench_extended.py --smoke --json build/extended-smoke.json

# Slots that dict lookups visit for keys that defeat a weak hash (tools/dictprobe.c): deterministic
# counts, so the run fails above a fixed limit; the timings it prints are for information only
# (it includes runtime.c, whose hash functions are runtime.py's: llvm-link adds those)
LLVMBIN = $(if $(PYSTACHY_LLVM),$(PYSTACHY_LLVM)/)
dictprobe: tools/dictprobe.c runtime.c runtime.py pystachy
	mkdir -p build
	./pystachy rt runtime.py -o build/dictprobe-rt.ll
	$(LLVMBIN)clang -O2 -S -emit-llvm tools/dictprobe.c -o build/dictprobe.ll
	$(LLVMBIN)llvm-link build/dictprobe-rt.ll build/dictprobe.ll -o build/dictprobe.bc
	$(LLVMBIN)clang -O2 build/dictprobe.bc -o build/dictprobe -lm
	build/dictprobe
	PYSTACHY_GC_STRESS=1 build/dictprobe --hash-cache

# A reachable empty list must release its historical backing, without allocating in clear.
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

# Inspect the bitcode passed to lli, then run it: dead functions must not reach code generation.
jitprobe: pystachy
	$(PY) tools/jitprobe.py

# Full verification (bootstrap, both compilers, the runtime cache, Python-free stage, UBSan, GC stress, IR check,
# benchmarks, dict probes, scaling) -> build/verification.json
verify:
	PY="$(PY)" tests/verify.sh

# IR oracle for refactors (tools/irsame.sh): ./pystachy must emit what the compiler of commit REF (default
# HEAD) emits -- IR, messages, exit status -- for every corpus program, or for FILES; irsame-py compares the
# CPython-hosted compilers. build/ref holds REF's pystachy.py, runtime.c, lib/ and stage-2 compiler, built
# as above and rebuilt only for another commit; each compiler uses the runtime.c and lib/ beside it.
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
	  { ! git cat-file -e $$c:runtime.py 2> /dev/null || git show $$c:runtime.py > build/ref/runtime.py; } && \
	  { ! git cat-file -e $$c:lib 2> /dev/null || git archive $$c lib | tar -xf - -C build/ref; } && \
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

# lib/re, run by CPython, must compile random patterns to CPython's code and errors and match, split
# and substitute as CPython's re, also on Pystachy's UTF-8 strs, and so must test_re's largest cases
# (tools/re_fuzz.py; deterministic: N=2000 patterns, SEED=1, e.g. make re-fuzz RE_FUZZ="20000 7")
RE_FUZZ ?=
re-fuzz:
	$(PY) tools/re_fuzz.py $(RE_FUZZ)

# ruff (findings only, ruff.toml), shellcheck of the scripts as POSIX sh, and clang's warnings on the C
# sources; pip install -r tools/requirements-dev.txt gives the versions CI uses
lint:
	ruff check
	shellcheck -s sh -S warning $(wildcard tests/*.sh tests/ffi/*.sh tools/*.sh bench/*.sh)
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror runtime.c tools/dictprobe.c tools/listprobe.c tools/eqprobe.c pyext.c pyembed.c
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror -DPYX_ABI3T pyext.c

clean:
	rm -rf build pystachy

.PHONY: test test-py test-cache test-ffi bench bench-extended bench-extended-check dictprobe listprobe eqprobe jitprobe verify irsame irsame-py ref check-ir check-runtime check-recordings re-fuzz lint clean
