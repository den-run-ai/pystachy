# listguard copies with a loop-invariant base (branch claude/dreamy-shannon-bb3cu1-listguard-base)

UMAP probe at 10,000 points (parent directory), AOT, pinned rounds; outputs identical. `stack` is
the runtime PR stack (#1436, #1437, #1442 on main `bf699eb`); `stacklg` adds this branch's first
version (base copies keeping a checked `b + i`), `stacklg2` the pushed one (plain `add nsw`).

Exact kNN stage ([bench_knn.sh](bench_knn.sh), 5 rounds each):

| Variant | Median |
|---|---:|
| stack | 2.997 s ([knn_round1.tsv](knn_round1.tsv)) |
| stacklg | 1.659 s, 1.632 s ([knn_round2.tsv](knn_round2.tsv)) |
| stacklg2 | 0.917 s |
| Numba, strict IEEE order | 0.736 s, 0.753 s |
| Numba, `fastmath=True` | 0.337 s |

The copy's inner loop is four instructions per element, unrolled four times with the items
pointers in registers, as Numba's strict loop is. With the checked add, its overflow exits kept
LLVM from hoisting the items pointer loads.

SGD layout ([layout_round1.tsv](layout_round1.tsv), 7 rounds): stack 4.178 s, Numba twin 4.166 s
(paired 1.004, faster in 3/7), umap-learn's own Numba kernel 4.527 s.

JIT (`pystachy run`, stack, 3 runs): kNN 7.6-7.9 s and layout 5.2-5.6 s, against AOT's 2.9-3.1 s and
4.1-4.2 s: the JIT tier calls each runtime function that AOT inlines.

The Lean access checker (tools/lean_boundary, built locally) rejects the new copies of
[tests/ir/list_guard_base.py](https://github.com/den-run-ai/pystachy/blob/088371b3/tests/ir/list_guard_base.py)
(`dist2`, `bump`): it has no fact for a sum of two registers.
