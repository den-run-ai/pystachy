"""Time the probe's layout kernel compiled by Numba, and umap-learn's own kernel, on one input.

Usage: numba_twin.py EXPORT_PATH twin|upstream
The twin is umap_core.optimize_layout's body over float64 NumPy arrays (no fastmath),
so its embedding should equal the Pystachy probe's bit for bit. The upstream mode runs
umap-learn's float32 compatibility kernel on the same graph and initial layout.
Prints one JSON line: the warm call's seconds (after a compiling call) and checksums.
"""

import json
import sys
import time

import numba
import numpy as np

CURVE_A = 1.5769434602697652
CURVE_B = 0.8950608778515733


@numba.njit
def clip(v):
    if v > 4.0:
        return 4.0
    if v < -4.0:
        return -4.0
    return v


@numba.njit
def tau_rand_int(state, base):
    s0 = state[base]
    s1 = state[base + 1]
    s2 = state[base + 2]
    s0 = (((s0 & 4294967294) << 12) & 0xFFFFFFFF) ^ ((((s0 & 0x7FFFF) << 13) ^ s0) >> 19)
    s1 = (((s1 & 4294967288) << 4) & 0xFFFFFFFF) ^ ((((s1 & 0x3FFFFFFF) << 2) ^ s1) >> 25)
    s2 = (((s2 & 4294967280) << 17) & 0xFFFFFFFF) ^ ((((s2 & 0x1FFFFFFF) << 3) ^ s2) >> 11)
    state[base] = s0
    state[base + 1] = s1
    state[base + 2] = s2
    r = (s0 ^ s1 ^ s2) & 0xFFFFFFFF
    return r - 4294967296 if r >= 2147483648 else r


@numba.njit
def optimize_layout(emb, head, tail, epochs_per_sample, n_vertices, n_epochs, rng_state,
                    a, b, gamma, initial_alpha, negative_sample_rate):
    n_edges = len(head)
    epochs_per_negative_sample = epochs_per_sample / negative_sample_rate
    epoch_of_next_negative_sample = epochs_per_negative_sample.copy()
    epoch_of_next_sample = epochs_per_sample.copy()
    updates = 0
    alpha = initial_alpha
    for n in range(n_epochs):
        for i in range(n_edges):
            if epoch_of_next_sample[i] > n:
                continue
            j = head[i]
            k = tail[i]
            dx = emb[j * 2] - emb[k * 2]
            dy = emb[j * 2 + 1] - emb[k * 2 + 1]
            dist_squared = dx * dx + dy * dy
            if dist_squared > 0.0:
                grad_coeff = -2.0 * a * b * pow(dist_squared, b - 1.0)
                grad_coeff /= a * pow(dist_squared, b) + 1.0
            else:
                grad_coeff = 0.0
            gx = clip(grad_coeff * dx)
            emb[j * 2] += gx * alpha
            emb[k * 2] += -gx * alpha
            gy = clip(grad_coeff * dy)
            emb[j * 2 + 1] += gy * alpha
            emb[k * 2 + 1] += -gy * alpha
            updates += 1
            epoch_of_next_sample[i] += epochs_per_sample[i]
            n_neg_samples = int(
                (n - epoch_of_next_negative_sample[i]) / epochs_per_negative_sample[i]
            )
            for _ in range(n_neg_samples):
                k = tau_rand_int(rng_state, j * 3) % n_vertices
                dx = emb[j * 2] - emb[k * 2]
                dy = emb[j * 2 + 1] - emb[k * 2 + 1]
                dist_squared = dx * dx + dy * dy
                if dist_squared > 0.0:
                    grad_coeff = 2.0 * gamma * b
                    grad_coeff /= (0.001 + dist_squared) * (a * pow(dist_squared, b) + 1)
                elif j == k:
                    continue
                else:
                    grad_coeff = 0.0
                if grad_coeff > 0.0:
                    emb[j * 2] += clip(grad_coeff * dx) * alpha
                    emb[j * 2 + 1] += clip(grad_coeff * dy) * alpha
                updates += 1
            epoch_of_next_negative_sample[i] += n_neg_samples * epochs_per_negative_sample[i]
        alpha = initial_alpha * (1.0 - (float(n) / float(n_epochs)))
    return updates


def load(path):
    with open(path) as f:
        lines = f.read().split("\n")
    head = [int(x) for x in lines[0].split()]
    n, dim, k, n_epochs = head[:4]
    floats = lambda s: np.array([float(x) for x in s.split()], dtype=np.float64)
    ints = lambda s: np.array([int(x) for x in s.split()], dtype=np.int64)
    return {"n": n, "n_epochs": n_epochs, "rng_seed": np.array(head[4:7], dtype=np.int64),
            "head": ints(lines[6]), "tail": ints(lines[7]), "weights": floats(lines[8]),
            "init": floats(lines[9]), "final": floats(lines[10])}


def main():
    e = load(sys.argv[1])
    mode = sys.argv[2]
    n, n_epochs = e["n"], e["n_epochs"]
    w = e["weights"]
    eps = float(n_epochs) / (float(n_epochs) * (w / w.max()))
    if mode == "twin":
        bits = e["init"][0::2].view(np.int64)
        rng0 = (e["rng_seed"][None, :] + bits[:, None]).ravel()

        def run():
            emb = e["init"].copy()
            updates = optimize_layout(emb, e["head"], e["tail"], eps, n, n_epochs, rng0.copy(),
                                      CURVE_A, CURVE_B, 1.0, 1.0, 5.0)
            return emb, updates
    else:
        import scipy.sparse
        from umap.layouts import optimize_layout_euclidean
        from umap.utils import make_epochs_per_sample

        graph = scipy.sparse.coo_matrix((w.astype(np.float32), (e["head"], e["tail"])), shape=(n, n))
        up_eps = make_epochs_per_sample(graph.data, n_epochs)

        def run():
            emb = e["init"].reshape(n, 2).astype(np.float32, order="C")
            optimize_layout_euclidean(
                emb, emb, graph.row, graph.col, n_epochs, n, up_eps, CURVE_A, CURVE_B,
                e["rng_seed"].copy(), gamma=1.0, initial_alpha=1.0, negative_sample_rate=5.0,
                parallel=False, move_other=True, optimizer="compatibility")
            return emb.astype(np.float64).ravel(), -1
    start = time.perf_counter()
    run()
    first = time.perf_counter() - start
    start = time.perf_counter()
    emb, updates = run()
    warm = time.perf_counter() - start
    print(json.dumps({"mode": mode, "first_call_s": round(first, 3), "warm_s": round(warm, 3),
                      "updates": int(updates), "embedding_sum": float(np.sum(emb)),
                      "equals_probe_bits": bool(np.array_equal(emb, e["final"]))}))


main()
