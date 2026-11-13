def dist(data: list[float], n: int, dim: int) -> float:
    best = 0.0
    for i in range(n):
        bi = i * dim
        for j in range(n):
            bj = j * dim
            s = 0.0
            for d in range(dim):
                diff = data[bi + d] - data[bj + d]
                s += diff * diff
            if s > best:
                best = s
    return best


xs = [float((k * 7919) % 101) / 7.0 for k in range(64 * 8)]
print(dist(xs, 64, 8))
