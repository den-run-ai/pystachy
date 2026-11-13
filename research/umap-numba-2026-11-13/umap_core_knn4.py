"""Feasibility probe: UMAP's compatibility-mode core in typed Python.

Follows umap-learn 0.6.0 (commit 17ce948) for Euclidean data with random
initialization: exact k-nearest neighbours, smooth_knn_dist,
compute_membership_strengths, the fuzzy union, make_epochs_per_sample and the
0.5.x ("compatibility") SGD layout with UMAP's Tausworthe generator. Values are
float64 throughout; upstream uses float32 arrays, so results agree only within
tolerance. Spectral initialization, NN-descent, other metrics, densMAP and the
estimator API are deliberately absent.

Usage: umap_core.py N DIM CENTERS K EPOCHS SEED [EXPORT_PATH]
"""

import math
import struct
import sys
import time
from random import Random

SMOOTH_K_TOLERANCE = 1e-5
MIN_K_DIST_SCALE = 1e-3
FLOAT_MAX = 3.4028234663852886e38  # NPY_FLOATMAX: float32's largest value
# find_ab_params(spread=1.0, min_dist=0.1) from umap-learn 0.6.0 (scipy curve_fit).
CURVE_A = 1.5769434602697652
CURVE_B = 0.8950608778515733


def to_float32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def float64_bits(x: float) -> int:
    return struct.unpack("<q", struct.pack("<d", x))[0]


def make_blobs(n: int, dim: int, centers: int, seed: int) -> list[float]:
    rng = Random(seed)
    means: list[float] = []
    for _ in range(centers * dim):
        means.append(rng.uniform(-10.0, 10.0))
    data: list[float] = []
    for i in range(n):
        c = i % centers
        for d in range(dim):
            data.append(to_float32(means[c * dim + d] + rng.gauss(0.0, 1.0)))
    return data


def knn_exact(data: list[float], n: int, dim: int, k: int) -> tuple[list[int], list[float]]:
    """Brute-force neighbours, ties to the lower index, as a stable argsort."""
    indices = [0] * (n * k)
    distances = [0.0] * (n * k)
    best_d = [0.0] * k
    best_i = [0] * k
    for i in range(n):
        filled = 0
        bi = i * dim
        for j in range(n):
            bj = j * dim
            s0 = 0.0
            s1 = 0.0
            s2 = 0.0
            s3 = 0.0
            d = 0
            while d + 4 <= dim:
                e0 = data[bi + d] - data[bj + d]
                e1 = data[bi + d + 1] - data[bj + d + 1]
                e2 = data[bi + d + 2] - data[bj + d + 2]
                e3 = data[bi + d + 3] - data[bj + d + 3]
                s0 += e0 * e0
                s1 += e1 * e1
                s2 += e2 * e2
                s3 += e3 * e3
                d += 4
            while d < dim:
                e0 = data[bi + d] - data[bj + d]
                s0 += e0 * e0
                d += 1
            s = (s0 + s1) + (s2 + s3)
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
            distances[i * k + m] = math.sqrt(best_d[m])
    return indices, distances


def smooth_knn_dist(
    distances: list[float], n: int, k: int, n_iter: int, local_connectivity: float
) -> tuple[list[float], list[float]]:
    target = math.log2(k)
    rho = [0.0] * n
    sigma = [0.0] * n
    total = 0.0
    count = 0
    for v in distances:
        if math.isfinite(v):
            total += v
            count += 1
    mean_distances = total / count if count > 0 else 0.0
    index = int(math.floor(local_connectivity))
    interpolation = local_connectivity - index
    for i in range(n):
        row = i * k
        non_zero: list[float] = []
        finite_sum = 0.0
        finite_count = 0
        for j in range(k):
            v = distances[row + j]
            if math.isfinite(v):
                finite_sum += v
                finite_count += 1
                if v > 0.0:
                    non_zero.append(v)
        if len(non_zero) >= local_connectivity:
            if index > 0:
                rho[i] = non_zero[index - 1]
                if interpolation > SMOOTH_K_TOLERANCE:
                    rho[i] += interpolation * (non_zero[index] - non_zero[index - 1])
            else:
                rho[i] = interpolation * non_zero[0]
        elif len(non_zero) > 0:
            rho[i] = max(non_zero)
        lo = 0.0
        hi = FLOAT_MAX
        mid = 1.0
        for _ in range(n_iter):
            psum = 0.0
            for j in range(1, k):
                d = distances[row + j] - rho[i]
                if d > 0:
                    psum += math.exp(-(d / mid))
                else:
                    psum += 1.0
            if math.fabs(psum - target) < SMOOTH_K_TOLERANCE:
                break
            if psum > target:
                hi = mid
                mid = (lo + hi) / 2.0
            else:
                lo = mid
                if hi >= FLOAT_MAX:
                    mid *= 2
                else:
                    mid = (lo + hi) / 2.0
        sigma[i] = mid
        if rho[i] > 0.0:
            floor = MIN_K_DIST_SCALE * (finite_sum / finite_count)
        else:
            floor = MIN_K_DIST_SCALE * mean_distances
        if sigma[i] < floor:
            sigma[i] = floor
    return sigma, rho


def fuzzy_graph(
    indices: list[int], distances: list[float], sigma: list[float], rho: list[float], n: int, k: int
) -> dict[int, float]:
    """compute_membership_strengths, then the fuzzy union P + P^T - P * P^T."""
    directed: dict[int, float] = {}
    for i in range(n):
        for j in range(k):
            col = indices[i * k + j]
            if col == -1 or col == i:
                continue  # missing neighbour, or the zero-weight self edge
            d = distances[i * k + j]
            if d - rho[i] <= 0.0 or sigma[i] == 0.0:
                val = 1.0
            else:
                val = math.exp(-((d - rho[i]) / sigma[i]))
            if val != 0.0:
                directed[i * n + col] = val
    union: dict[int, float] = {}
    for key, v in directed.items():
        i = key // n
        j = key % n
        w = directed.get(j * n + i, 0.0)
        u = v + w - v * w
        if u != 0.0:
            union[key] = u
            union[j * n + i] = u
    return union


def edge_arrays(
    union: dict[int, float], n: int, n_epochs: int
) -> tuple[list[int], list[int], list[float]]:
    """Row-major COO edges after UMAP's pruning of weights below max / n_epochs."""
    max_weight = 0.0
    for v in union.values():
        if v > max_weight:
            max_weight = v
    threshold = max_weight / float(n_epochs)
    head: list[int] = []
    tail: list[int] = []
    weights: list[float] = []
    for key in sorted(union.keys()):
        v = union[key]
        if v < threshold:
            continue
        head.append(key // n)
        tail.append(key % n)
        weights.append(v)
    return head, tail, weights


def make_epochs_per_sample(weights: list[float], n_epochs: int) -> list[float]:
    result = [-1.0] * len(weights)
    if len(weights) == 0:
        return result
    max_weight = max(weights)
    for e in range(len(weights)):
        n_samples = float(n_epochs) * (weights[e] / max_weight)
        if n_samples > 0.0:
            result[e] = float(n_epochs) / n_samples
    return result


def random_init(n: int, seed: int) -> list[float]:
    """Uniform(-10, 10) coordinates rescaled into [0, 10] per axis, as float32 values."""
    rng = Random(seed + 1)
    emb = [0.0] * (n * 2)
    for i in range(n * 2):
        emb[i] = rng.uniform(-10.0, 10.0)
    for d in range(2):
        lo = emb[d]
        hi = emb[d]
        for i in range(n):
            v = emb[i * 2 + d]
            lo = min(lo, v)
            hi = max(hi, v)
        for i in range(n):
            emb[i * 2 + d] = to_float32(10.0 * (emb[i * 2 + d] - lo) / (hi - lo))
    return emb


def tau_rand_int(state: list[int], base: int) -> int:
    """UMAP's Tausworthe step with Numba's int64 wraparound and int32 result."""
    s0 = state[base]
    s1 = state[base + 1]
    s2 = state[base + 2]
    # (s << c) & 0xFFFFFFFF keeps only bits below 32, so mask before shifting
    # instead of relying on int64 wraparound.
    s0 = (((s0 & 4294967294) << 12) & 0xFFFFFFFF) ^ ((((s0 & 0x7FFFF) << 13) ^ s0) >> 19)
    s1 = (((s1 & 4294967288) << 4) & 0xFFFFFFFF) ^ ((((s1 & 0x3FFFFFFF) << 2) ^ s1) >> 25)
    s2 = (((s2 & 4294967280) << 17) & 0xFFFFFFFF) ^ ((((s2 & 0x1FFFFFFF) << 3) ^ s2) >> 11)
    state[base] = s0
    state[base + 1] = s1
    state[base + 2] = s2
    r = (s0 ^ s1 ^ s2) & 0xFFFFFFFF
    return r - 4294967296 if r >= 2147483648 else r


def clip(v: float) -> float:
    if v > 4.0:
        return 4.0
    if v < -4.0:
        return -4.0
    return v


def optimize_layout(
    emb: list[float],
    head: list[int],
    tail: list[int],
    epochs_per_sample: list[float],
    n_vertices: int,
    n_epochs: int,
    rng_seed: list[int],
    a: float,
    b: float,
    gamma: float,
    initial_alpha: float,
    negative_sample_rate: float,
) -> int:
    """The 0.5.x compatibility SGD, with move_other=True and two dimensions."""
    n_edges = len(head)
    rng_state = [0] * (n_vertices * 3)
    for v in range(n_vertices):
        bits = float64_bits(emb[v * 2])
        for c in range(3):
            rng_state[v * 3 + c] = rng_seed[c] + bits
    epochs_per_negative_sample = [x / negative_sample_rate for x in epochs_per_sample]
    epoch_of_next_negative_sample = list(epochs_per_negative_sample)
    epoch_of_next_sample = list(epochs_per_sample)
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
            gy = clip(grad_coeff * dy)  # dimension 1 is untouched by the update above
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


def write_floats(out, values: list[float]) -> None:
    out.write(" ".join([repr(v) for v in values]) + "\n")


def write_ints(out, values: list[int]) -> None:
    out.write(" ".join([str(v) for v in values]) + "\n")


def main() -> None:
    n = int(sys.argv[1])
    dim = int(sys.argv[2])
    centers = int(sys.argv[3])
    k = int(sys.argv[4])
    n_epochs = int(sys.argv[5])
    seed = int(sys.argv[6])
    t0 = time.perf_counter()
    data = make_blobs(n, dim, centers, seed)
    t1 = time.perf_counter()
    indices, distances = knn_exact(data, n, dim, k)
    t2 = time.perf_counter()
    sigma, rho = smooth_knn_dist(distances, n, k, 64, 1.0)
    union = fuzzy_graph(indices, distances, sigma, rho, n, k)
    head, tail, weights = edge_arrays(union, n, n_epochs)
    epochs_per_sample = make_epochs_per_sample(weights, n_epochs)
    t3 = time.perf_counter()
    emb = random_init(n, seed)
    init = list(emb)
    rng_seed = [seed * 7919 + 1, seed * 104729 + 2, seed * 1299709 + 3]
    updates = optimize_layout(
        emb, head, tail, epochs_per_sample, n, n_epochs, rng_seed,
        CURVE_A, CURVE_B, 1.0, 1.0, 5.0,
    )
    t4 = time.perf_counter()
    checksum = 0.0
    for v in emb:
        checksum += v
    print(f"points={n} dim={dim} k={k} epochs={n_epochs} edges={len(head)} updates={updates}")
    print(f"sigma[0]={sigma[0]!r} rho[0]={rho[0]!r} weight_sum={math.fsum(weights)!r}")
    print(f"embedding_sum={checksum!r} first={emb[0]!r},{emb[1]!r}")
    print(
        f"seconds data={t1 - t0:.3f} knn={t2 - t1:.3f} graph={t3 - t2:.3f} layout={t4 - t3:.3f}",
        file=sys.stderr,
    )
    if len(sys.argv) > 7:
        with open(sys.argv[7], "w") as out:
            write_ints(out, [n, dim, k, n_epochs, rng_seed[0], rng_seed[1], rng_seed[2]])
            write_floats(out, data)
            write_ints(out, indices)
            write_floats(out, distances)
            write_floats(out, sigma)
            write_floats(out, rho)
            write_ints(out, head)
            write_ints(out, tail)
            write_floats(out, weights)
            write_floats(out, init)
            write_floats(out, emb)


main()
