# key= as CPython runs it: sorted() and list.sort() call the key on every item first, in order,
# and then compare the keys (an __lt__ that prints shows the order); min() and max() call the key
# and compare item by item. While list.sort() computes the keys the list is empty; a key that
# raises leaves it as it was, one that changes it makes the sort fail, and a comparison that
# raises leaves the items in the order the sort reached.


class K:
    def __init__(self, v: int) -> None:
        self.v = v

    def __lt__(self, o: "K") -> bool:
        print(f"  {self.v}<{o.v}", end="")
        if self.v == 99 or o.v == 99:
            raise ValueError("no order for 99")
        return self.v < o.v

    def __gt__(self, o: "K") -> bool:
        print(f"  {self.v}>{o.v}", end="")
        return self.v > o.v


def key(n):
    print(f" key({n})", end="")
    return K(n % 7)


def to_k(n):
    return K(n)


print(sorted([10, 3, 8, 1], key=key))
print(min([10, 3, 8, 1], key=key))
print(max([10, 3, 8, 1], key=key))
print(min(4, 9, 2, key=key))

xs = [5, 1, 4]
watch = xs


def peek(n):
    print(f" sees {len(watch)}", end="")
    return n


xs.sort(key=peek)
print(" ->", xs)


def bad_key(n):
    if n == 4:
        raise KeyError(n)
    return n


ys = [5, 1, 4, 2]
try:
    ys.sort(key=bad_key)
except KeyError as e:
    print("key raised", e, ys)

zs = [3, 1, 2]


def grow(n):
    zs.append(n)
    return n


try:
    zs.sort(key=grow)
except ValueError as e:
    print(e, zs)

ws = [6, 99, 2, 5, 1]
try:
    ws.sort(key=to_k)
except ValueError as e:
    print("\ncomparison raised:", e, ws)
vs = [6, 99, 2, 5, 1]
try:
    vs.sort(key=to_k, reverse=True)
except ValueError as e:
    print("\nreversed, comparison raised:", e, vs)
none: list[int] = []
try:
    print(min(none, key=key))
except ValueError as e:
    print(e)
try:
    print(max(none, key=to_k))
except ValueError as e:
    print(e)


# the keyword arguments are evaluated when the call is: after the generator expression's iterable,
# before its items are made
def item(x):
    print(f" item({x})", end="")
    return x


def rev() -> bool:
    print(" reverse", end="")
    return True


def make_key(tag):
    print(f" make_key({tag})", end="")
    return key


print(sorted((item(x) for x in [3, 1, 2]), reverse=rev()))
print(sorted((item(x) for x in [3, 1, 2]), key=make_key(1), reverse=rev()))
print(sorted(range(3), reverse=rev()), max([5, 6], key=make_key(2)))

# and after a list comprehension has run
print(sorted([item(x) for x in [3, 1, 2]], reverse=rev()))
print(max([item(x) for x in [5, 6]], key=make_key(3)), min([item(x) for x in [5, 6]], key=make_key(4)))
