# itertools' iterators that end with their input (lib/_pystachy_itertools.py): accumulate(),
# batched(), chain() and chain.from_iterable(), compress(), dropwhile(), filterfalse(),
# pairwise(), starmap() and takewhile(), over lists, strings, tuples, dicts, sets, generators and
# iterator objects; each reads its input as it is iterated, one item at a time.
import operator
from itertools import accumulate, batched, chain, compress, dropwhile, filterfalse, pairwise, starmap, takewhile
from collections.abc import Iterator


def letters(word: str) -> Iterator[str]:
    for c in word:
        print("  read", c)
        yield c


def numbers(n: int) -> Iterator[int]:
    for i in range(n):
        print("  read", i)
        yield i


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self):
        return self

    def __next__(self) -> int:
        if self.n == 0:
            raise StopIteration
        self.n -= 1
        return self.n


empty: list[int] = []

# accumulate(): sums, a function of two arguments, an initial value
data = [3, 4, 6, 2, 1, 9, 0, 7, 5, 8]
print(list(accumulate(data)), list(accumulate(data, max)), list(accumulate(data, min)))
print(list(accumulate(data, operator.mul)), list(accumulate(data, func=operator.sub)))
print(list(accumulate(["a", "b", "c"])), list(accumulate([[1], [2], [3]])), list(accumulate((1.5, 2.25))))
print(list(accumulate([1, 2, 3], initial=100)), list(accumulate(empty, initial=5)), list(accumulate(empty)))
print(list(accumulate([1, 2, 3], lambda a, b: a * 10 + b, initial=9)), list(accumulate("abc", initial="")))
print(list(accumulate([True, False, True])), list(accumulate([True, True], initial=10)), list(accumulate([False])))
print(list(accumulate(Countdown(4))), list(accumulate({1: "a", 2: "b"})))
update = lambda balance, payment: round(balance * 1.05) - payment
print(list(accumulate([90] * 10, update, initial=1000)))
acc = accumulate(numbers(3))
print("made")
print(next(acc), next(acc), list(acc))

# batched(): tuples of n items, the last one shorter (or ValueError with strict=True)
print(list(batched("ABCDEFG", 3)), list(batched([1, 2, 3, 4], 2)), list(batched((1.5,), 4)), list(batched(empty, 3)))
print(list(batched("ab", 1)), list(batched(Countdown(5), n=2)), list(batched([1, 2, 3, 4], 2, strict=True)))
bt = batched(letters("abcde"), 2)
print("made")
print(next(bt))
print(list(bt))
try:
    for b in batched([1, 2, 3], 2, strict=True):
        print(b)
except ValueError as e:
    print("ValueError:", e)
for n in (0, -1):
    try:
        batched("abc", n)
    except ValueError as e:
        print("ValueError:", e)
try:
    batched("abc", 2.0)
except TypeError as e:
    print("TypeError:", e)

# chain() and chain.from_iterable(): the iterables need not be of one type, their items must be
print(list(chain("ABC", "DEF")), list(chain([1, 2], (3, 4), {5: "x"}, {6}, Countdown(2))), list(chain()))
print(list(chain("a")), list(chain(empty, empty, [1])), list(chain(numbers(2), [10, 20])))
print(list(chain.from_iterable(["ABC", "DEF"])), list(chain.from_iterable([[1], [], [2, 3]])))
print(list(chain.from_iterable(letters(w) for w in ["xy", "z"])))
ch = chain(letters("ab"), letters("c"))
print("made")
print(next(ch))
print(list(ch))
print(chain)

# compress(): the data items whose selectors are true, until either input ends
print(list(compress("ABCDEF", [1, 0, 1, 0, 1, 1])), list(compress([1, 2, 3, 4], [True, False])), list(compress("ab", "x ")))
print(list(compress(letters("abc"), [0, 0])), list(compress([1, 2, 3], numbers(2))))

# dropwhile(), takewhile(), filterfalse(): a predicate's verdicts, with filterfalse(None, ...)
print(list(dropwhile(lambda x: x < 5, [1, 4, 6, 3, 8])), list(takewhile(lambda x: x < 5, [1, 4, 6, 3, 8])))
print(list(filterfalse(lambda x: x < 5, [1, 4, 6, 3, 8])), list(filterfalse(None, [0, 1, 0, 2, 3])), list(filterfalse(bool, ["", "a", ""])))
print(list(dropwhile(str.isspace, "  x y")), list(takewhile(str.isalpha, "ab1c")), list(filterfalse(str.isdigit, "a1b2")))
print(list(dropwhile(lambda x: True, [1, 2])), list(takewhile(lambda x: False, [1, 2])), list(dropwhile(lambda x: x, empty)))
tw = takewhile(lambda c: c != "c", letters("abcd"))
print(list(tw), list(tw))
dw = dropwhile(lambda c: c != "c", letters("abcd"))
print("made")
print(list(dw))

# pairwise() and starmap()
print(list(pairwise("ABCDEFG")), list(pairwise([1])), list(pairwise(empty)), list(pairwise(Countdown(3))))
print(list(pairwise(letters("abc"))))
print(list(starmap(pow, [(2, 5), (3, 2), (10, 3)])), list(starmap(max, [(1, 5), (7, 2)])))
print(list(starmap(lambda s, n: s * n, [("a", 2), ("b", 3)])), list(starmap(divmod, [(7, 2)])))
print(list(starmap(lambda: 1, [(), ()])), list(starmap(operator.add, [(1, 10), (2, 20)])))
