# Coherent compiler build publication

`self_pipeline.py --publish-manifest /path/stage1.json` publishes a compiler and
its retained raw IR as one generation. Both files are copied into a unique
`stage1.json.generations/generation-*` directory, checked against the hashes
recorded by the build, and made read-only. One atomic replacement of
`stage1.json` makes the generation visible to readers. The manifest binds the
source hash, validation mode, both file sizes and both SHA-256 hashes.

Use the manifest as the next compiler input:

```sh
python bench/compiler_host/self_pipeline.py \
  --hosted --backend ordinary --overlap --jobs 2 \
  --llvm /path/llvm/bin --work /tmp/stage1-work \
  --report /tmp/stage1-report.json --publish-manifest /tmp/stage1.json

python bench/compiler_host/self_pipeline.py \
  --compiler-manifest /tmp/stage1.json --backend ordinary --overlap --jobs 2 \
  --llvm /path/llvm/bin --work /tmp/stage2-work \
  --report /tmp/stage2-report.json --publish-manifest /tmp/stage2.json
```

Each work directory must be new. These commands keep local compiler/runtime
IR witnesses enabled. The existing bootstrap controller may instead delegate
all six witnesses with `--caller-witnesses`; its manifest explicitly records
`caller-witnesses`, which does **not** establish a verified bootstrap.

Programmatic consumers call `resolve_publication(path)` once and retain its
`compiler` and `raw_ir` paths. Resolution rejects unsupported schemas, invalid
generation names, symlinked publication components, altered sizes/hashes and
nonexecutable compilers. `require_witnesses=True` also rejects a generation
whose witness checks were delegated to the caller. The next-stage CLI records
the exact consumed manifest hash and generation, even if another writer later
replaces the pointer.

## Failure and concurrency contract

- A copy, validation or pre-replacement failure leaves the previous manifest
  usable. Unique staging permits concurrent publishers without mixed artifacts.
- A reader that already resolved a generation keeps using its immutable files.
  The publisher never modifies or deletes previous generations.
- Once replacement is attempted, the complete generation is retained even if
  interruption makes the result ambiguous. This can leave an unreferenced
  directory; it cannot remove files a reader may already have observed.
- `--output` and `--emit-ir` remain optional compatibility outputs with individual
  atomic replacement. A consumer needing a coherent pair must use the manifest.
  Failure during those legacy copies prevents publication of a new manifest.
- Reports are diagnostic outputs and can lag a committed manifest. Read the
  manifest to determine the currently published generation.

This protocol assumes trusted local storage. It provides atomic visibility,
not crash-durable multi-file transactions, hostile-writer protection, remote
authentication, garbage collection or a complete cross-host cache identity.
Do not collect a generation until every reader that may have pinned it has
finished. The unit tests inject copy/replace failures and concurrent publication;
the opt-in LLVM tests also consume a published compiler in a second build.
