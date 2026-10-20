# lib/random.py's integer and sequence methods against CPython's: randrange() in its one-, two- and
# three-argument forms (negative steps, 63-bit widths), randint(), choice(), shuffle(), sample()
# (the pool and the set selection, counts=), choices() (weights, cum_weights, k=0) over many seeds,
# on lists of ints, floats, strs (non-ASCII) and objects, strs and runtime-length tuples, with the
# module's functions, and CPython's errors and messages
import random
from random import Random


class Card:
    def __init__(self, rank: int, suit: str) -> None:
        self.rank = rank
        self.suit = suit

    def __repr__(self) -> str:
        return f"Card({self.rank}, {self.suit!r})"


print("randrange and randint")
for s in [0, 1, -3, 99, 2**40 + 3, 9223372036854775807]:
    r = Random(s)
    print(s, [r.randrange(10) for i in range(8)], [r.randrange(1) for i in range(3)])
    print([r.randrange(-5, 5) for i in range(8)], [r.randrange(3, 4) for i in range(3)])
    print([r.randrange(0, 100, 7) for i in range(6)], [r.randrange(100, 0, -9) for i in range(6)])
    print([r.randrange(-1, -50, -2) for i in range(6)], [r.randrange(5, 6, 10) for i in range(3)])
    print([r.randint(1, 6) for i in range(12)], [r.randint(-2, -2) for i in range(2)])
    print(r.randrange(2**62), r.randrange(9223372036854775807), r.randrange(-2**62, 2**62 - 1),
          r.randint(-4611686018427387904, 4611686018427387902),
          r.randrange(1, 9223372036854775805, 3))
    print(r.randrange(10, step=1), r.randrange(True, 5), r.randint(False, True),
          r.randrange(10, None))

print("choice")
r = Random(7)
words = ["alpha", "beta", "gamma", "delta", "épsilon", "ζήτα", "η"]
print([r.choice(words) for i in range(10)])
print([r.choice([1.5, 2.5, -0.5]) for i in range(5)], [r.choice("abcdef") for i in range(6)])
runtime_tuple: tuple[int, ...] = tuple([10, 20, 30, 40])
print([r.choice(runtime_tuple) for i in range(6)], r.choice([True, False]))
cards = [Card(1, "hearts"), Card(2, "hearts"), Card(12, "spades"), Card(13, "clubs")]
print([r.choice(cards) for i in range(4)])
print([r.choice([[1], [2, 3]]) for i in range(4)])

print("shuffle")
for s in [0, 1, 2, 3, 12345, -12345]:
    r = Random(s)
    xs = list(range(20))
    r.shuffle(xs)
    names = ["Ann", "Bob", "Çelik", "Dana", "Émile"]
    r.shuffle(names)
    one = [5]
    r.shuffle(one)
    none: list[str] = []
    r.shuffle(none)
    print(s, xs, names, one, none)
deck = list(cards)
Random(4).shuffle(deck)
print(deck)
big = list(range(1000))
Random(10).shuffle(big)
print(big[:10], big[-10:], sum(big), sorted(big) == list(range(1000)))

print("sample")
for s in [0, 1, 5, 77]:
    r = Random(s)
    print(s, r.sample(list(range(10)), 3), r.sample(list(range(10)), 10),
          r.sample(list(range(10)), 0))
    # n <= setsize: the pool; else the set of selections
    print(r.sample(list(range(21)), 5), r.sample(list(range(22)), 5), r.sample(list(range(100)), 6),
          r.sample(list(range(1000)), 12))
    print(r.sample(words, 4), r.sample("abcdefgh", 3), r.sample(runtime_tuple, 2))
    print(r.sample(["red", "blue"], counts=[4, 2], k=5),
          r.sample(["x", "y", "z"], k=4, counts=[0, 2, 3]))
    print(r.sample(list(range(5000)), k=20)[:5], len(r.sample(list(range(5000)), k=4000)))
nothing: list[int] = []
print(Random(1).sample(nothing, 0), Random(1).sample(nothing, k=0, counts=nothing))
# counts sample range(total): its pool where total is small, else a set of k selections, and no
# list of total ints
r = Random(9)
print(r.sample(["a", "b"], counts=[30, 40], k=10), r.sample(["a", "b"], counts=[300, 400], k=10),
      r.sample(["a", "b"], counts=[5, 0], k=5))
print(r.sample(["red", "blue"], counts=[10**15, 10**15], k=5),
      r.sample(["x", "y", "z"], counts=[3 * 10**18, 1, 6 * 10**18], k=40))

print("choices")
for s in [0, 1, 8, 2024]:
    r = Random(s)
    print(s, r.choices(words, k=5), r.choices([1, 2, 3]), r.choices([1, 2, 3], k=0))
    print(r.choices(["a", "b", "c"], [10, 1, 1], k=6),
          r.choices(["a", "b", "c"], [0.5, 0.0, 2.5], k=6))
    print(r.choices(["a", "b", "c"], cum_weights=[1, 1, 5], k=6),
          r.choices(["a", "b", "c"], cum_weights=[0.25, 0.5, 0.75], k=4))
    print(r.choices(["a", "b", "c"], [True, False, True], k=4), r.choices(cards, k=2))
r = Random(3)
counts = {"a": 0, "b": 0, "c": 0}
for c in r.choices(["a", "b", "c"], [1, 2, 7], k=10000):
    counts[c] += 1
print(counts)

print("module functions")
random.seed(42)
print(random.randrange(100), random.randint(1, 10), random.choice(words))
xs = list(range(10))
random.shuffle(xs)
print(xs, random.sample(xs, 4), random.choices(xs, k=4), random.choices(xs, xs, k=3))


def attempt(label: str, f) -> None:
    try:
        print(label, f())
    except (ValueError, TypeError, IndexError) as e:
        print(label, type(e).__name__, e)


print("errors")
r = Random(1)
empty: list[int] = []
attempt("randrange(0)", lambda: r.randrange(0))
attempt("randrange(-3)", lambda: r.randrange(-3))
attempt("randrange(5, 5)", lambda: r.randrange(5, 5))
attempt("randrange(7, 2)", lambda: r.randrange(7, 2))
attempt("randrange(5, 5, 2)", lambda: r.randrange(5, 5, 2))
attempt("randrange(0, 10, -3)", lambda: r.randrange(0, 10, -3))
attempt("randrange(1, 5, 0)", lambda: r.randrange(1, 5, 0))
attempt("randrange(10, None, 2)", lambda: r.randrange(10, None, 2))
attempt("randrange(10, step=True)", lambda: r.randrange(10, step=True))
attempt("randrange(10, None, 1.0)", lambda: r.randrange(10, None, 1.0))
attempt("randint(5, 4)", lambda: r.randint(5, 4))
attempt("choice([])", lambda: r.choice(empty))
attempt("choice('')", lambda: r.choice(""))
attempt("sample(k=4)", lambda: r.sample([1, 2, 3], 4))
attempt("sample(k=-1)", lambda: r.sample([1, 2, 3], -1))
attempt("sample(set)", lambda: r.sample({1, 2, 3}, 2))
attempt("sample(dict)", lambda: r.sample({1: 2}, 1))
attempt("counts length", lambda: r.sample([1, 2], 1, counts=[1]))
attempt("counts negative", lambda: r.sample([1, 2], 1, counts=[1, -5]))
attempt("counts k", lambda: r.sample([1, 2], 5, counts=[1, 2]))
attempt("counts floats", lambda: r.sample([1, 2], 1, counts=[1.0, 2.0]))
attempt("choices both", lambda: r.choices([1, 2], [1, 2], cum_weights=[1, 3]))
attempt("choices length", lambda: r.choices([1, 2], [1]))
attempt("cum_weights length", lambda: r.choices([1, 2], cum_weights=[1, 2, 3]))
attempt("choices zero", lambda: r.choices([1, 2], [0, 0]))
attempt("choices negative", lambda: r.choices([1, 2], [1.0, -3.0]))
attempt("choices inf", lambda: r.choices([1, 2], [1.0, float("inf")]))
attempt("choices nan", lambda: r.choices([1, 2], [1.0, float("nan")]))
attempt("choices empty", lambda: r.choices(empty, k=2))
attempt("choices empty k=0", lambda: r.choices(empty, k=0))
attempt("choices empty weights", lambda: r.choices(empty, empty))
