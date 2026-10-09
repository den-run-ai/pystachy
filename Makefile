# Bootstrap: CPython runs pystachy.py on itself (stage 1); that native compiler rebuilds
# itself (stage 2) and must reproduce its own LLVM IR byte for byte (fixed point).
PY ?= python3

pystachy: pystachy.py runtime.c
	mkdir -p build
	$(PY) pystachy.py build pystachy.py -o build/pystachy1
	build/pystachy1 build pystachy.py -o build/pystachy2
	$(PY) pystachy.py ir pystachy.py -o build/stage1.ll
	build/pystachy1 ir pystachy.py -o build/stage2.ll
	build/pystachy2 ir pystachy.py -o build/stage3.ll
	cmp build/stage1.ll build/stage2.ll && cmp build/stage2.ll build/stage3.ll
	@echo "fixed point: stage1 == stage2 == stage3 ($$(wc -l < build/stage1.ll) lines of IR)"
	cp build/pystachy2 pystachy

test: pystachy
	tests/run.sh ./pystachy

test-py:
	tests/run.sh "$(PY) pystachy.py"

bench: pystachy
	PY="$(PY)" bench/run.sh

# Slots that dict lookups visit for keys that defeat a weak hash (tools/dictprobe.c): deterministic
# counts, so the run fails above a fixed limit; the timings it prints are for information only
dictprobe: tools/dictprobe.c runtime.c
	mkdir -p build
	$(if $(PYSTACHY_LLVM),$(PYSTACHY_LLVM)/)clang -O2 tools/dictprobe.c -o build/dictprobe -lm
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
	  { ! git cat-file -e $$c:lib 2> /dev/null || git archive $$c lib | tar -xf - -C build/ref; } && \
	  PYSTACHY_HOME= $(PY) build/ref/pystachy.py build build/ref/pystachy.py -o build/ref/pystachy1 && \
	  PYSTACHY_HOME= build/ref/pystachy1 build build/ref/pystachy.py -o build/ref/pystachy && \
	  echo $$c > build/ref/commit; \
	fi

# llvm-as must accept the IR of every corpus program that compiles, or of FILES (tools/check_ir.sh)
check-ir: pystachy
	tools/check_ir.sh ./pystachy $(FILES)

# the compiler's RUNTIME table must agree with runtime.c (tools/check_runtime.py)
check-runtime:
	$(PY) tools/check_runtime.py

clean:
	rm -rf build pystachy

.PHONY: test test-py bench dictprobe verify irsame irsame-py ref check-ir check-runtime clean
