# listguard with a start or a step that a register gives: the tests before the loop check
# start + c >= 0 for the smallest c an index adds, stop <= len(xs) - c for each list's largest c and
# a variable step's sign, and run a copy whose inline item reads and stores carry TBAA tags (.tbaa)
def eliminate(a: list[float], b: list[float], j: int, f: float) -> None:
    for k in range(j + 1, len(a)):
        a[k] -= f * b[k]


def stepped(a: list[int], lo: int, step: int) -> int:
    s = 0
    for i in range(lo, len(a), step):
        s += a[i - 1]
    return s


x = [1.0, 2.0, 3.0]
eliminate(x, [4.0, 5.0, 6.0], 0, 0.5)
print(x, stepped([1, 2, 3, 4], 1, 2))
