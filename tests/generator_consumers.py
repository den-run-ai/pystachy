# generator expressions as the argument of consumers; any() and all() stop at the deciding item
import os

xs = [3, 1, 2]
print(sum(x * 2 for x in xs), min(x for x in xs), max(x for x in xs))
print(sorted(x for x in xs), list(x + 1 for x in xs), sorted((x for x in xs), reverse=True))
print(any(x > 2 for x in xs), all(x > 0 for x in xs))
print(", ".join(str(x) for x in xs))
ys: list[int] = []
ys.extend(x * 10 for x in xs)
print(ys)
p = "generator_consumers_" + str(os.getpid()) + ".txt"
with open(p, "w") as w:
    w.write("one\ntwo\nthree\n")
f = open(p)
print(any(f), repr(f.readline()))
f.close()
g = open(p)
print(all(g), repr(g.readline()))
g.close()
os.remove(p)
print(any(range(10**12)), all(range(10**12)))
print(any(enumerate(["a"])), all(zip([0], [1])), any(reversed([0, 0, 1])))
print(any(range(0)), all(range(0)), any(range(1)), all(range(1, 5)))


def noisy(n: int) -> int:
    print("noisy", n)
    return n


print(sum((noisy(x) for x in [1, 2]), noisy(10)), sum((x * 1.5 for x in [1, 2]), 0.5))
