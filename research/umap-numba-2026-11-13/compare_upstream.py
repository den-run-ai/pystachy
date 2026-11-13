"""Compare the probe's export with umap-learn's own Numba kernels on the same inputs.

Usage: compare_upstream.py EXPORT_PATH STAGE [REPEATS]
STAGE: graph | layout-serial | layout-parallel | knn | quality
Timings exclude the first (JIT-compiling) call, which is reported separately.
"""

import json
import sys
import time

import numpy as np


def load(path):
    with open(path) as f:
        lines = f.read().split("\n")
    head = [int(x) for x in lines[0].split()]
    n, dim, k, n_epochs = head[:4]
    rng_seed = np.array(head[4:7], dtype=np.int64)
    floats = lambda s: np.array([float(x) for x in s.split()], dtype=np.float64)
    ints = lambda s: np.array([int(x) for x in s.split()], dtype=np.int64)
    return {
        "n": n, "dim": dim, "k": k, "n_epochs": n_epochs, "rng_seed": rng_seed,
        "data": floats(lines[1]).reshape(n, dim),
        "indices": ints(lines[2]).reshape(n, k),
        "distances": floats(lines[3]).reshape(n, k),
        "sigma": floats(lines[4]), "rho": floats(lines[5]),
        "head": ints(lines[6]), "tail": ints(lines[7]), "weights": floats(lines[8]),
        "init": floats(lines[9]).reshape(n, 2), "final": floats(lines[10]).reshape(n, 2),
    }


def upstream_graph(e):
    import umap.umap_ as uu

    X = e["data"].astype(np.float32)
    graph, sigmas, rhos = uu.fuzzy_simplicial_set(
        X, e["k"], np.random.RandomState(0), "euclidean",
        knn_indices=e["indices"], knn_dists=e["distances"].astype(np.float32),
    )
    coo = graph.tocoo()
    coo.sum_duplicates()
    coo.data[coo.data < (coo.data.max() / float(e["n_epochs"]))] = 0.0
    coo.eliminate_zeros()
    return coo, sigmas, rhos


def time_calls(fn, repeats):
    start = time.perf_counter()
    fn()
    first = time.perf_counter() - start
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return first, samples


def run_layout(e, coo, parallel):
    from umap.layouts import optimize_layout_euclidean
    from umap.umap_ import find_ab_params
    from umap.utils import make_epochs_per_sample

    a, b = find_ab_params(1.0, 0.1)
    emb = e["init"].astype(np.float32, order="C")
    eps = make_epochs_per_sample(coo.data, e["n_epochs"])
    optimize_layout_euclidean(
        emb, emb, coo.row, coo.col, e["n_epochs"], e["n"], eps, a, b, e["rng_seed"].copy(),
        gamma=1.0, initial_alpha=1.0, negative_sample_rate=5.0, parallel=parallel,
        move_other=True, optimizer="compatibility",
    )
    return emb


def quality(e, emb):
    from sklearn.neighbors import NearestNeighbors

    k = e["k"]
    high = e["indices"][:, 1:]  # exact neighbours without the point itself
    nn = NearestNeighbors(n_neighbors=k).fit(emb)
    low = nn.kneighbors(emb, return_distance=False)[:, 1:]
    preserved = np.mean([len(set(h) & set(l)) / (k - 1) for h, l in zip(high, low)])
    labels = np.arange(e["n"]) % 10
    votes = labels[low]
    predicted = np.array([np.bincount(v, minlength=10).argmax() for v in votes])
    return {"knn_preservation": float(preserved), "label_knn_accuracy": float(np.mean(predicted == labels))}


def main():
    e = load(sys.argv[1])
    stage = sys.argv[2]
    repeats = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    out = {"stage": stage}
    if stage == "graph":
        first, samples = time_calls(lambda: upstream_graph(e), repeats)
        coo, sigmas, rhos = upstream_graph(e)
        probe_edges = set(zip(e["head"].tolist(), e["tail"].tolist()))
        up_edges = set(zip(coo.row.tolist(), coo.col.tolist()))
        order = np.lexsort((coo.col, coo.row))
        same = probe_edges == up_edges
        out.update(
            first_call_s=first, warm_s=samples,
            sigma_max_rel_diff=float(np.max(np.abs(sigmas - e["sigma"]) / np.abs(e["sigma"]))),
            rho_max_abs_diff=float(np.max(np.abs(rhos - e["rho"]))),
            edges_probe=len(probe_edges), edges_upstream=len(up_edges), same_edge_set=same,
            weight_max_abs_diff=float(np.max(np.abs(coo.data[order] - e["weights"]))) if same else None,
        )
    elif stage in ("layout-serial", "layout-parallel"):
        coo, _, _ = upstream_graph(e)
        parallel = stage == "layout-parallel"
        first, samples = time_calls(lambda: run_layout(e, coo, parallel), repeats)
        out.update(first_call_s=first, warm_s=samples)
    elif stage == "knn":
        import umap.umap_ as uu

        X = e["data"].astype(np.float32)
        fn = lambda: uu.nearest_neighbors(X, e["k"], "euclidean", {}, False, np.random.RandomState(0))
        first, samples = time_calls(fn, repeats)
        idx = fn()[0]
        recall = np.mean([len(set(a) & set(b)) / e["k"] for a, b in zip(idx, e["indices"])])
        out.update(first_call_s=first, warm_s=samples, recall_vs_exact=float(recall))
    elif stage == "quality":
        coo, _, _ = upstream_graph(e)
        out["probe_float64"] = quality(e, e["final"])
        out["upstream_serial_float32"] = quality(e, run_layout(e, coo, False))
        out["random_init"] = quality(e, e["init"])
    print(json.dumps(out))


main()
