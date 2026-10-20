# map() and filter() where a consumer takes their items (list(), sorted(), sum(), min(), max(),
# any(), all(), str.join(), list.extend(), ...): the generator expressions they are, their function
# evaluated first, the items made one by one as the consumer asks (any() and all() stop early)
def note(tag, v):
    print("eval", tag)
    return v


def sq(x: int) -> int:
    return x * x


xs = [3, 1, 2]
words = ["b", "A", "c"]
print(list(map(sq, xs)), sorted(map(str.lower, words)), sum(map(sq, xs)), max(map(len, words)))
print("-".join(map(str, xs)), list(filter(None, [0, 1, 2, 0, 3])), list(filter(lambda v: v % 2 == 1, xs)))
print(any(map(lambda v: v > 2, xs)), all(map(bool, xs)), list(map(lambda a, b: a * b, xs, [10, 20, 30])))
print(sum(map(sq, xs), 100), min(map(len, words)))
out: list[str] = []
out.extend(map(str.upper, words))
print(out, list(map(int, "1 2 3".split())))
print(sorted(map(note("f", sq), note("xs", xs)), key=note("k", lambda v: -v)))


def big(v: int) -> bool:
    print(" test", v)
    return v > 2


print(any(map(big, [1, 5, 2, 7])), all(map(big, [3, 1, 9])))
pairs = list(map(lambda k, v: f"{k}={v}", ["a", "b", "c"], [1, 2]))
print(pairs, list(filter(str.isdigit, ["1", "x", "22"])), list(map(abs, [-1, 2, -3])))
