# Inherited descriptor clobber in the JIT launcher

Reproduced on main `6e5544cfa3eecb8329e4f4cb19d2e0ac3e99b1bf`, Linux x86-64,
CPython 3.13.16, LLVM 18.1.3. `current-main-results.json` uses the CPython-hosted
compiler from that exact main tree. `results.json` uses the separately bootstrapped
native compiler from networking draft `9c2d9e5`; all compiler/runtime/library
sources match main. The optional networking bridge is absent from this probe.

The parent writes `PIPE` to a pipe and passes its read endpoint as descriptor
8, 9 or 64. The program opens `/dev/fd/N`, reads four bytes and prints their hex.
CPython and AOT print `50495045` at all three descriptors. JIT silently prints
ELF bytes `7f454c46` for descriptor 8 and bitcode bytes `4243c0de` for descriptor
9; descriptor 64 succeeds. Every recorded process exits zero without stderr.

`src/pystachy_compiler/driver.py` opens its own files using `exec 9< ... 8< ...`
before entering `lli`; CPython embedding also uses descriptor 7. This overwrites
inherited application resources. A selector on a replaced pipe reports EPERM,
which first exposed the problem in real compiler stdout/stderr collection.

Reproduce with:

```sh
python3.13 research/network-io-inherited-fds/reproduce.py
```

The networking dogfood launcher can duplicate its inherited pipes to descriptor
64 and above as an explicit prototype workaround. That does not fix arbitrary
programs using existing descriptor numbers. This research branch is evidence
for a separate compiler-driver fix and must not be merged as-is.
