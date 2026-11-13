# listguard: a range loop whose item reads and assignments a test of each list's length before
# it proves in range runs a copy with no runtime list call (.calls) whose inline list reads and
# stores carry the TBAA tags of an items pointer and of an item, as length loads carry a length's
# (.tbaa), so that LLVM can vectorize it; a loop that changes a list's length keeps its checks and
# gets no copy
def stencil(a: list[float], b: list[float]) -> None:
    for i in range(1, len(a) - 1):
        b[i] = (a[i - 1] + a[i] + a[i + 1]) / 3.0


def grow(a: list[float]) -> float:
    s = 0.0
    for i in range(len(a)):
        s += a[i]
        a.append(1.0)
    return s


out = [0.0, 0.0, 0.0]
stencil([1.0, 2.0, 3.0], out)
print(out, grow([1.0, 2.0]))
