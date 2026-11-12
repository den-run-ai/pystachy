# heapq follows CPython's C module, which CPython imports over heapq.py: a sifted item trades
# places with each item it passes, so a comparison that changes the heap finds all of its items
# there, a size change raises RuntimeError, an empty heap's IndexError reads "index out of
# range", and heapify() of more than 2500 items compares in its cache-friendly order
import heapq

ACT = ""
WHEN = -1
SEEN = 0


class H:
    def __init__(self, v: int) -> None:
        self.v = v

    def __lt__(self, o: "H") -> bool:
        global WHEN, SEEN
        SEEN = (SEEN * 31 + self.v * 7 + o.v) % 1000000007
        if WHEN == 0:
            if ACT == "clear":
                heap.clear()
            elif ACT == "append":
                heap.append(H(99))
            elif ACT == "replace":
                heap[0] = H(50)
        WHEN -= 1
        return self.v < o.v


heap: list[H] = []


def fill(vs: list[int], act: str, when: int) -> None:
    global ACT, WHEN
    heap.clear()
    for v in vs:
        heap.append(H(v))
    ACT = act
    WHEN = when


def show(label: str) -> None:
    print(label, [h.v for h in heap])


for act in ["clear", "append", "replace"]:
    for when in [0, 1]:
        fill([1, 3, 2, 7, 5, 4, 6], act, when)
        try:
            heapq.heappush(heap, H(0))
            show(f"push {act} {when}")
        except RuntimeError as e:
            show(f"push {act} {when} RuntimeError: {e}")
        fill([1, 3, 2, 7, 5, 4, 6], act, when)
        try:
            print(heapq.heappop(heap).v)
            show(f"pop {act} {when}")
        except (RuntimeError, IndexError) as e:
            show(f"pop {act} {when} {type(e).__name__}: {e}")
        fill([9, 3, 8, 1, 5, 2, 6], act, when)
        try:
            heapq.heapify(heap)
            show(f"heapify {act} {when}")
        except RuntimeError as e:
            show(f"heapify {act} {when} RuntimeError: {e}")
        fill([1, 3, 2, 7, 5, 4, 6], act, when)
        try:
            print(heapq.heappushpop(heap, H(4)).v)
            show(f"pushpop {act} {when}")
        except (RuntimeError, IndexError) as e:
            show(f"pushpop {act} {when} {type(e).__name__}: {e}")

empty: list[int] = []
for name in ["heappop", "heapreplace"]:
    try:
        print(heapq.heappop(empty) if name == "heappop" else heapq.heapreplace(empty, 1))
    except IndexError as e:
        print(name, "IndexError:", e)
print(heapq.heappushpop(empty, 5))

big: list[H] = []
x = 7
for _ in range(3001):
    x = (x * 1103515245 + 12345) % 2147483648
    big.append(H(x % 1000))
WHEN = -1
SEEN = 0
heap = big
heapq.heapify(heap)
print("heapify 3001", SEEN, [h.v for h in heap[:8]])
SEEN = 0
print(heapq.heappop(heap).v, heapq.heapreplace(heap, H(500)).v, SEEN)
