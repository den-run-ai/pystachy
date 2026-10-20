# itertools' checks of an argument's type, which its type decides at compile time, raise
# CPython's TypeError as the program runs, and the call keeps the type of the iterator it would
# return: permutations()' r of another type than int, count() of something other than a number,
# and islice() and tee() with too few or too many arguments; an optional int or number is checked
# for None as the program runs
from itertools import batched, count, islice, permutations, product, repeat, tee
from typing import Optional


def attempt(label: str, f) -> None:
    try:
        print(label, "ok", f())
    except (TypeError, ValueError) as e:
        print(label, type(e).__name__, e)


attempt("permutations float", lambda: list(permutations("abc", 2.0)))
attempt("permutations str", lambda: list(permutations("abc", "2")))
attempt("permutations None", lambda: len(list(permutations("abc", None))))
attempt("permutations negative", lambda: list(permutations("abc", -2)))
r: Optional[int] = None
attempt("permutations Optional None", lambda: len(list(permutations("abcd", r))))
r = 2
attempt("permutations Optional 2", lambda: len(list(permutations("abcd", r))))
attempt("count str", lambda: list(islice(count("a"), 2)))
attempt("count step str", lambda: next(count(1, "a")))
attempt("count None", lambda: next(count(None)))
attempt("islice no index", lambda: list(islice("abc")))
attempt("islice five", lambda: list(islice("abc", 1, 2, 3, 4)))
attempt("tee three", lambda: [list(t) for t in tee("abc", 1, 2)])


def unpack():
    a, b = tee("abc", 2, 3)
    return list(a)


attempt("tee three unpacked", unpack)


def maybe(n: int) -> Optional[int]:
    return None if n < 0 else n


for n in [-1, 2]:
    attempt(f"count {n}", lambda: list(islice(count(maybe(n)), 3)))
    attempt(f"count step {n}", lambda: list(islice(count(1, maybe(n)), 3)))
    attempt(f"batched {n}", lambda: list(batched("abcde", maybe(n))))
    attempt(f"repeat {n}", lambda: list(repeat("a", maybe(n))))
    attempt(f"product {n}", lambda: len(list(product("ab", repeat=maybe(n)))))
    attempt(f"tee {n}", lambda: len(tee("ab", maybe(n))))
for c in count("x"):
    print(c)
