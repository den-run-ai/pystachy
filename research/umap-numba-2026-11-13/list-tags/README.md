# Shared list alias tags (#1442)

Against main `bf699eb5`, same host as the parent directory. `tbaa` is the PR's compiler (hosted
under CPython, which emits the native compiler's IR); outputs equal main's everywhere.

Instructions (callgrind, whole process, [bench-callgrind.txt](bench-callgrind.txt)): `bench/`
programs nbody −2.13%, list_reads −3.73%, itertools_loops −0.67%, dictkeys −0.38%, words −0.25%,
the other ten within ±0.02%. [`scatter_loop.py`](scatter_loop.py) (item stores through computed
indexes between reads of other lists) −5.8%. The UMAP probe at 2,000 points: +0.7% alone (its
layout loop still calls the opaque `pys_fpow`, and without the length `!range` +1.6%), and
7,940,345,874 with the float-power PR (#1436) against that PR's 8,026,439,578 (−1.1%).

Wall time, paired medians of pinned rotated rounds ([timing.txt](timing.txt)): nbody 0.962 (6/7),
scatter 0.945 (5/7), UMAP probe process 0.984 (5/5), its layout stage 1.018 (2/5, within noise).

Negative control: the same retag with distinct struct names (`@listX`, `@slotX`), so that LLVM
takes runtime and compiled list accesses for disjoint, makes `list_tag_alias`'s `twin(p, p, 30)`
print 8330 instead of CPython's 9200 (AOT): a store through one name no longer reaches a read
through the other. The PR's shared tags print 9200 (JIT, AOT, GC stress), as main does.
