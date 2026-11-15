# Independent review: optional tuple storage repair

**No blocking finding** in frozen tree `107460d5f89bdcf37f2741b233eac0568d82604a`, based on `94f472d6de5350fc9481ecf3b9ec019d2ecdb4f2`. I verified all four working files, frozen copies and git blobs against the receipt and patch. The change affects the Python storage adapter, its tests and storage documentation.

The source-layout changes preserve the original representation through optional nested tuple loads and pack/unpack transport. Boundary comparison admits same optionality and pointer-preserving optional widening while still creating each integer-width obligation; removal of child optionality, scalar representation changes and arity mismatch stay refused.

Absence facts are attached to the actual null branch or an executed literal-null child store. Every later nested store first clears descendant fit, marker and digit facts. Both the initial cell inventory and the late phi-edge inventory expand these resets, including stack tuples. The patch retains dominance validation, simultaneous phi semantics, exception edges and the existing restrictions on alias/raw tuple stores. The facts express absent-or-valid-encoding; they do not prove a dereference safe.

I reviewed the final **69/69 passing tests with no skips**, including independent real-IR narrowing/null-test/copy-guard bypasses, literal-null versus unknown/present replacements, branch-dependent stores, and late phi-edge cells on both heap and stack tuples. The final tests are bound to the same frozen file hashes. Their old-adapter run fails as expected, with 12 selected test methods and retained subtest failures/errors.

The focused target now proves **142/142 storage obligations**, with no unsupported, rejected, unclassified or error result. The formerly unknown functions contribute 50 obligations in main.init, 76 in exercise and 8 in read_nested, alongside the previous eight counted obligations. Its newly inspected typed-after-only snapshot is explicitly distinguished from the historical full-census snapshot; I do not call this exact-census replay.

This is code and focused-evidence approval. The completed 94f4 census remains a preserved strict-storage failure, and the repaired source needs final full qualification. I ran no compiler, runtime or Lean checker. No compiler, runtime, corpus or Lean theorem source changed, and the existing model trust boundaries remain.
