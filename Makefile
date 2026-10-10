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

test: pystachy
	tests/run.sh ./pystachy

# the CPython-hosted compiler runs as a module, whose bytecode CPython caches (it compiles a script's
# 16k lines again at every start); the cache is checked against pystachy.py's hash, not its mtime
test-py:
	$(PY) -c 'import py_compile as c; c.compile("pystachy.py", doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH)'
	tests/run.sh "$(PY) -m pystachy" "jit aot" $(FILES)

bench: pystachy
	PY="$(PY)" bench/run.sh

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

# Full verification (bootstrap, both compilers, Python-free stage, UBSan, GC stress, IR check, benchmarks, dict probes,
# scaling) -> build/verification.json
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

# ruff (findings only, ruff.toml), shellcheck of the scripts as POSIX sh, and clang's warnings on the C
# sources; pip install -r tools/requirements-dev.txt gives the versions CI uses
lint:
	ruff check
	shellcheck -s sh -S warning $(wildcard tests/*.sh tools/*.sh bench/*.sh)
	$(LLVMBIN)clang -fsyntax-only -Wall -Wextra -Werror runtime.c tools/dictprobe.c

clean:
	rm -rf build pystachy

.PHONY: test test-py bench dictprobe verify irsame irsame-py ref check-ir check-runtime lint clean
