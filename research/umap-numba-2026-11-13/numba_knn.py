"""Time the probe's exact kNN under Numba (strict and fastmath) on the exported data.

Usage: numba_knn.py EXPORT_PATH strict|fastmath
The body is umap_core.knn_exact over flat float64/int64 arrays. Strict mode keeps the
source's summation order, as Pystachy must; fastmath lets LLVM reassociate (and so vectorize).
"""

import json
import sys
import time

import numba
import numpy as np


def knn_exact(data, n, dim, k):
    indices = np.zeros(n * k, dtype=np.int64)
    distances = np.zeros(n * k, dtype=np.float64)
    best_d = np.zeros(k, dtype=np.float64)
    best_i = np.zeros(k, dtype=np.int64)
    for i in range(n):
        filled = 0
        bi = i * dim
        for j in range(n):
            bj = j * dim
            s = 0.0
            for d in range(dim):
                diff = data[bi + d] - data[bj + d]
                s += diff * diff
            if filled < k:
                pos = filled
                filled += 1
            elif s < best_d[k - 1]:
                pos = k - 1
            else:
                continue
            while pos > 0 and best_d[pos - 1] > s:
                best_d[pos] = best_d[pos - 1]
                best_i[pos] = best_i[pos - 1]
                pos -= 1
            best_d[pos] = s
            best_i[pos] = j
        for m in range(k):
            indices[i * k + m] = best_i[m]
            distances[i * k + m] = np.sqrt(best_d[m])
    return indices, distances


def main():
    with open(sys.argv[1]) as f:
        lines = f.read().split("\n")
    n, dim, k = [int(x) for x in lines[0].split()[:3]]
    data = np.array([float(x) for x in lines[1].split()], dtype=np.float64)
    want = np.array([int(x) for x in lines[2].split()], dtype=np.int64)
    fn = numba.njit(fastmath=sys.argv[2] == "fastmath")(knn_exact)
    fn(data[: 64 * dim], 64, dim, k)  # compile
    start = time.perf_counter()
    idx, _ = fn(data, n, dim, k)
    warm = time.perf_counter() - start
    print(json.dumps({"mode": sys.argv[2], "warm_s": round(warm, 3),
                      "same_neighbours_as_probe": bool(np.array_equal(idx, want))}))


main()
