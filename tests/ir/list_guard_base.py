# listguard with a base: a range loop whose item reads and assignments add to the loop's index a
# base that no iteration changes (a local the loop never stores, as bi and bj) runs, where tests
# before the loop find base + start >= 0 and stop + base <= len(xs) - c for each list, a copy
# with no runtime list call and no overflow check of base + index (.calls); a loop that stores
# its base keeps its checks and gets no copy
def dist2(data: list[float], i: int, j: int, dim: int) -> float:
    bi = i * dim
    bj = j * dim
    s = 0.0
    for d in range(dim):
        diff = data[bi + d] - data[bj + d]
        s += diff * diff
    return s


def bump(ys: list[int], b: int, n: int) -> None:
    for k in range(n):
        ys[b + k + 1] = ys[b + k] + k


def moving(xs: list[int], n: int) -> int:
    b = 0
    t = 0
    for k in range(n):
        t += xs[b + k]
        b = b - 1
    return t


ys = [1, 2, 3, 4]
bump(ys, 0, 3)
print(dist2([1.0, 2.0, 3.0, 4.0], 0, 1, 2), ys, moving([5, 6, 7], 2))
