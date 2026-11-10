# Alpha.3 boundary integration audit

This is an evidence record for PR #1215, not code intended for `main`.

Baseline: `070c8137edeb610e11d8d81653e506ad64a9ce6d`.
Candidate: `ac32fee7bb9116138bf90727f9c4e83e76eaf84b`.
Candidate tree: `449fd986435afedfab929aa60feef587811883f0`.
The candidate preserves PRs #1211, #1212, #1213 and #1214.

## Result

The full 4,395-input hosted corpus comparison used CPython 3.13.16,
`PYSTACHY_IRCHECK=1`, two workers, and each compiler's own library/runtime.
There were no changed exit statuses, substantive diagnostics, missing outputs,
or newly rejected existing inputs. After the narrow path canonicalization below,
4,385 inputs match and ten retain IR differences. The oracle therefore exits 1;
it is not being described as a zero-difference run.

Eight residual cases import the changed TOML implementation. The other two,
`lib_gettext.py` and `sys_prefix.py`, encode their installation directory. All ten
were separately compared with both compilers using the same candidate library
and runtime; every IR byte, diagnostic and status then matched. The library
change was exposed by the full separate-library run, rather than hidden by that
bounded attribution control. The only executable library source change is
`lib/tomllib/_parser.py`.

`summary.json` names every residual and every normalized input. The full oracle
log includes every differing case, with the stock bounded first-hunk display.
The residual-control log records complete byte equality for those ten cases.

Local `make check-fast` completed 666 tests with 22 tool-dependent skips.
The exact-head PR matrix passed all 19 applicable checks; same-repository DCO
was skipped. Native bootstrap, JIT/AOT/GC and executable Lean validation are CI
evidence, not local execution: the local LLVM and Lean toolchains were absent.

## Checkout-path handling

The frozen `oracle-old` and `oracle-new` checkouts have equal-length names and
retain distinct source/library trees. The wrapper resolves the shared input,
output and fixture-search paths before changing into the selected checkout.
It inherits the explicitly selected IR verifier setting.

The wrapper canonicalizes only a single own-library prefix inside a private
LLVM string global beginning with `cannot import name `. It does not change
constant IDs, string lengths, instructions, module/member names, suffix paths,
or other message bytes. All prefixes are 47 bytes in this recorded workspace.
The real import-error emitters, loader and diagnostic code are unchanged between
the two commits. No source literal collides with these audit paths.

The normalization affected 253 unique corpus inputs. Old/new rewrite counts
match for every input. Two repeated entries are the initial `byte_bpe.py` and
`lib_tomllib_flags.py` controls; these are not additional corpus inputs.
Independent controls verified that symbol, member, module, suffix-path, length
and message changes remain differences, and that nonmatching strings, instruction
rows, two-prefix rows and foreign prefixes remain untouched.

The reporting copy of `tools/irsame.sh` changes only its corpus working directory,
explicit diagnostic-library prefixes and the number of differing cases displayed.
Its comparison, exit-status, missing-output and worker logic is unchanged.
The occasional broken-pipe text comes from the stock bounded diff display;
it does not bypass comparisons or the differing-case result.

## Reproduction details

The scripts retain the actual workspace paths used, and their SHA-256 hashes are
recorded in `summary.json`. To replay elsewhere, adapt the corpus/log destinations
and create equal-length `oracle-old`/`oracle-new` checkout names. Preserve the
separate libraries and all comparison logic.

The full run invokes the reporting script with these two compiler commands,
under `PYSTACHY_IRCHECK=1 PYSTACHY_JOBS=2`:

```
python compare_compiler_home.py /path/to/oracle-old
python compare_compiler_home.py /path/to/oracle-new
```

For the ten residual inputs only, stock `tools/irsame.sh` compares
`python /path/to/oracle-old/pystachy.py` with
`python /path/to/oracle-new/pystachy.py`, setting
`PYSTACHY_HOME=/path/to/oracle-new` for both. Native correctness remains covered
by the separately linked CI matrix and the CPython differential corpus.
