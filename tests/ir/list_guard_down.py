# listguard where a loop counts down: its index runs from start down to stop + 1, so the tests
# before it bound start + 1 by each list's length and stop + 1 + c below by 0, and its copy's item
# reads carry TBAA tags (.tbaa). A loop whose last index is -1, which wraps, keeps that read checked
def back(x: list[float], hi: int) -> float:
    s = 0.0
    for i in range(hi, -1, -1):
        s = s * 0.5 + x[i]
    return s


def pairs(a: list[int], hi: int, lo: int) -> int:
    s = 0
    for i in range(hi, lo, -2):
        s += a[i] * a[i - 1]
    return s


def based(data: list[int], b: int, hi: int) -> int:
    s = 0
    for i in range(hi, 0, -1):
        s += data[b + i]
    return s


def wraps(a: list[int]) -> int:
    s = 0
    for i in range(len(a) - 1, -2, -1):
        s = s * 2 + a[i]
    return s


print(back([1.0, 2.0, 3.0], 2), pairs([1, 2, 3, 4, 5], 4, 0), based([1, 2, 3, 4], 1, 2), wraps([1, 2, 3]))
