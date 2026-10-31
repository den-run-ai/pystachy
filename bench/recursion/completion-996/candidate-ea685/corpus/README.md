# Independent assessment of the retained corpus diagnostics

All 29 diagnostic differences left unresolved by the frozen comparison are own-checkout path substitutions. They contain **74 source-location tokens per compiler**, including the leading error location and nested specialization/call-stack locations. The ten referenced complete library files are byte-identical between current main and the candidate. Their relative paths, line numbers, source lines, and every byte outside the checkout prefixes match.

The original comparison remains **`status: failed`, `gate_passed: false`**. It recorded all 3,924 cases, with no missing cases, validation failures, or status changes. Of 61 raw diagnostic differences, its narrow leading-location normalizer accepted 32. It rejected these 29 because the error-message bytes themselves contain further absolute checkout paths. This assessment explains those retained differences separately; it does not change the original normalizer or rerun either compiler.

## Evidence

| Record | Identity |
| --- | --- |
| Current main | `07b26e02425d023288ed95a9d2a5077be5aeb45e` |
| Candidate | `ea68529b8a590eb8f3df7200b857e1d16becd7a3` |
| Original comparison SHA256 | `425b47eb39da4d4dabfe5ec4c0a8be63d6536bb38e23ee338c88238300b2d2a6` |
| Frozen comparison harness SHA256 | `2da54d464e5d560e77fc32ce45b659d69b25e82e2b8267c6d8c337ded6887ee7` |
| Assessment SHA256 | `84c42011b80f0d393102b52eb252cb3c35bfdb91afc37772ef884e8cf7d79b72` |

`assessment.json` includes all 29 original stdout/stderr byte strings as lossless UTF-8 JSON strings, their original paths and SHA256 hashes, original per-case record hashes, every replaced token's byte spans, both raw tokens, relative file and line number, and the referenced source line. Its source-file table records each side's full-file SHA256, size, original input-manifest match, exact committed Git blob identity, and successful byte comparison. `diagnostic-source-files.diff` is the empty exact Git diff of those ten files between the two pinned commits.

The controller checks every occurrence of each own-home prefix, rejects unrecognized occurrences and opposite-home paths, validates each source file against both the retained input manifest and the pinned Git revision, then reconstructs diagnostics by replacing only validated path prefixes. It requires the token sequence and all residual bytes to match. Original report, harness, build records, case records, streams, and referenced files are hash-checked before and after the audit.

## Reproduce

Run from the restored workspace after making the pinned source checkouts and original evidence available at their recorded paths:

```sh
python3 experiments/assess_corpus_diagnostics.py \
  --report experiments/corpus-ea685/comparison.json \
  --out /tmp/pystachy-corpus-diagnostic-assessment
```

The output directory must be new. The script only reads the original evidence and Git objects; it writes the separate assessment directory. It invokes no compiler, LLVM tool, or workload. An independent byte-span replay of the self-contained assessment is also available:

```sh
python3 experiments/verify_assessed_diagnostics.py \
  --assessment experiments/corpus-ea685-assessment/assessment.json
```

This assessment covers diagnostic equivalence under proven checkout-prefix substitutions. It makes no claim that the 2,139 changed raw IR outputs are byte-identical or semantically equivalent, and it does not decide performance acceptance or merge readiness.
