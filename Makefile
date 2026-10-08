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

# Full verification (bootstrap, both compilers, Python-free stage, UBSan, benchmarks) -> build/verification.json
verify:
	PY="$(PY)" tests/verify.sh

clean:
	rm -rf build pystachy

.PHONY: test test-py bench dictprobe verify clean
