import sys
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
import heapq
from typing import Callable


def b_int_loop(n: int) -> int:
    t = 0
    for i in range(n):
        t += (i * i) % 7 + (i >> 3) - (i & 5)
    return t


def b_float_loop(n: int) -> float:
    x = 0.5
    t = 0.0
    for i in range(n):
        x = x * 1.0000001 + 0.000001
        t += x * x - x / 3.0
    return t


def b_list_append_pop(n: int) -> int:
    xs: list[int] = []
    for i in range(n):
        xs.append(i)
    t = 0
    while xs:
        t += xs.pop()
    return t


def b_list_comp(n: int) -> int:
    t = 0
    for r in range(20):
        xs = [i * 2 for i in range(n // 20)]
        ys = [x + 1 for x in xs if x % 3 == 0]
        t += sum(ys) + len(xs)
    return t


def b_dict_str(n: int) -> int:
    words = ["w" + str(i % 5000) for i in range(n)]
    d: dict[str, int] = {}
    for w in words:
        d[w] = d.get(w, 0) + 1
    return len(d) + d["w42"]


def b_dict_int(n: int) -> int:
    d: dict[int, int] = {}
    for i in range(n):
        k = (i * 7919) % 100003
        if k in d:
            d[k] += 1
        else:
            d[k] = 1
    t = 0
    for k in d:
        t += d[k]
    return t + len(d)


def b_dict_tuple(n: int) -> int:
    d: dict[tuple[int, int], int] = {}
    for i in range(n):
        k = (i % 300, i % 7)
        d[k] = d.get(k, 0) + i
    return len(d) + d[(5, 5)]


def b_set_ops(n: int) -> int:
    a = set(range(0, n, 2))
    b = set(range(0, n, 3))
    c = a & b
    d = a | b
    e = a - b
    t = 0
    for i in range(n):
        if i in c:
            t += 1
    return t + len(d) + len(e)


def b_str_concat(n: int) -> int:
    s = ""
    for i in range(n):
        s += "ab"
    return len(s)


def b_str_join_split(n: int) -> int:
    t = 0
    for r in range(n // 2000):
        parts = [str(i) for i in range(200)]
        s = ",".join(parts)
        back = s.split(",")
        t += len(s) + len(back)
    return t


def b_fstring(n: int) -> int:
    t = 0
    for i in range(n):
        s = f"{i}:{i * 2:>8}|{i / 7:.3f}"
        t += len(s)
    return t


def b_str_index(n: int) -> int:
    s = "the quick brown fox jumps over the lazy dog " * 50
    t = 0
    m = len(s)
    for i in range(n):
        if s[i % m] == "o":
            t += 1
    return t


def b_str_index_unicode(n: int) -> int:
    s = "thé quick brøwn fox jumps över the lazy dog " * 50
    t = 0
    m = len(s)
    for i in range(n):
        if s[(i * 7919) % m] == "o":
            t += 1
    return t


def b_str_slice(n: int) -> int:
    s = "the quick brown fox jumps over the lazy dog " * 5
    t = 0
    m = len(s) - 10
    for i in range(n):
        t += len(s[i % m : i % m + 8])
    return t


class Pt:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def norm2(self) -> float:
        return self.x * self.x + self.y * self.y

    def add(self, o: "Pt") -> "Pt":
        return Pt(self.x + o.x, self.y + o.y)


def b_method_calls(n: int) -> float:
    p = Pt(0.0, 0.0)
    d = Pt(0.001, 0.002)
    t = 0.0
    for i in range(n):
        p = p.add(d)
        t += p.norm2()
    return t


class Animal:
    def __init__(self, w: int) -> None:
        self.w = w

    def speak(self) -> int:
        return self.w


class Dog(Animal):
    def speak(self) -> int:
        return self.w * 2


class Cat(Animal):
    def speak(self) -> int:
        return self.w + 3


class Cow(Animal):
    def speak(self) -> int:
        return self.w - 1


def b_virtual(n: int) -> int:
    zoo: list[Animal] = []
    for i in range(1000):
        if i % 4 == 0:
            zoo.append(Dog(i))
        elif i % 4 == 1:
            zoo.append(Cat(i))
        elif i % 4 == 2:
            zoo.append(Cow(i))
        else:
            zoo.append(Animal(i))
    t = 0
    for r in range(n // 1000):
        for a in zoo:
            t += a.speak()
    return t


def b_closure(n: int) -> int:
    def make(k: int):
        def f(x: int) -> int:
            return x + k

        return f

    fs = [make(i) for i in range(10)]
    t = 0
    for i in range(n):
        t += fs[i % 10](i)
    return t


def gen_range(n: int):
    for i in range(n):
        yield i


def gen_sq(it):
    for x in it:
        yield (x * x) % 1000


def gen_odd(it):
    for x in it:
        if x % 2:
            yield x


def b_generators(n: int) -> int:
    return sum(gen_odd(gen_sq(gen_range(n))))


def b_genexp(n: int) -> int:
    return sum((x * x) % 1000 for x in range(n) if x % 3)


def b_exceptions(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            if i % 4 == 0:
                raise ValueError("x")
            t += 1
        except ValueError:
            t += 2
    return t


def b_keyerror(n: int) -> int:
    d: dict[int, int] = {i: i for i in range(0, 1000, 2)}
    t = 0
    for i in range(n):
        try:
            t += d[i % 1000]
        except KeyError:
            t -= 1
    return t


def b_sort_ints(n: int) -> int:
    xs = [(i * 7919 + 13) % 1000003 for i in range(n)]
    xs.sort()
    return xs[0] + xs[n // 2] + xs[-1]


def b_sort_key(n: int) -> int:
    xs = [(i * 7919 + 13) % 1000003 for i in range(n)]
    ys = sorted(xs, key=lambda v: (v % 1000, -v))
    return ys[0] + ys[n // 2] + ys[-1]


def b_sort_str(n: int) -> int:
    xs = [str((i * 7919 + 13) % 1000003) for i in range(n)]
    xs.sort()
    return len(xs[0]) + int(xs[n // 2]) + int(xs[-1])


def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


def b_fib(n: int) -> int:
    return fib(n)


def divmod2(a: int, b: int) -> tuple[int, int]:
    return a // b, a % b


def b_tuple_ret(n: int) -> int:
    t = 0
    for i in range(1, n):
        q, r = divmod2(i * 3, 7)
        t += q - r
    return t


@dataclass
class Rec:
    a: int
    b: str
    c: float


def b_dataclass(n: int) -> float:
    rs = [Rec(i, "n" + str(i % 10), i * 0.5) for i in range(n)]
    t = 0.0
    for r in rs:
        t += r.a + r.c + len(r.b)
    return t


def b_union(n: int) -> int:
    xs: list[int | str] = []
    for i in range(1000):
        if i % 3 == 0:
            xs.append(str(i))
        else:
            xs.append(i)
    t = 0
    for r in range(n // 1000):
        for x in xs:
            if isinstance(x, int):
                t += x
            else:
                t += len(x)
    return t


def b_str_methods(n: int) -> int:
    lines = ["  Key%d = Value %d ; comment  " % (i, i * 3) for i in range(200)]
    t = 0
    for r in range(n // 200):
        for line in lines:
            s = line.strip()
            if s.startswith("Key") and "=" in s:
                k, _, v = s.partition("=")
                v = v.split(";")[0].strip().lower()
                t += len(k.rstrip()) + v.find("e") + len(v.replace("value", "v"))
    return t


def b_int_str(n: int) -> int:
    t = 0
    for i in range(n):
        t += int(str(i * 37)) % 11
    return t


def b_matmul(n: int) -> float:
    a = [[float(i * j % 7) for j in range(n)] for i in range(n)]
    b = [[float((i + j) % 5) for j in range(n)] for i in range(n)]
    c = [[0.0] * n for _ in range(n)]
    for i in range(n):
        ai = a[i]
        ci = c[i]
        for k in range(n):
            aik = ai[k]
            bk = b[k]
            for j in range(n):
                ci[j] += aik * bk[j]
    return c[n // 2][n // 3] + c[0][0] + c[n - 1][n - 1]


def b_deque_heap(n: int) -> int:
    dq: deque[int] = deque()
    for i in range(n):
        dq.append(i)
        if i % 3 == 0:
            dq.popleft()
    h: list[int] = []
    for i in range(n // 4):
        heapq.heappush(h, (i * 7919) % 10007)
    t = 0
    while h:
        t += heapq.heappop(h)
    return t + len(dq)


def b_optional(n: int) -> int:
    d: dict[int, int] = {i: i * 2 for i in range(0, 1000, 3)}
    t = 0
    for i in range(n):
        v = d.get(i % 1000)
        if v is not None:
            t += v
    return t


def b_dot(n: int) -> float:
    xs = [i * 0.5 for i in range(1000)]
    ys = [i * 0.25 for i in range(1000)]
    t = 0.0
    for r in range(n // 1000):
        s = 0.0
        for i in range(len(xs)):
            s += xs[i] * ys[i]
        t += s
    return t


def b_bfs(n: int) -> int:
    grid = [[(i * 7 + j * 13) % 11 != 0 for j in range(n)] for i in range(n)]
    dist = [[-1] * n for _ in range(n)]
    q: deque[tuple[int, int]] = deque()
    q.append((0, 1))
    dist[0][1] = 0
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < n and 0 <= ny < n and grid[nx][ny] and dist[nx][ny] < 0:
                dist[nx][ny] = dist[x][y] + 1
                q.append((nx, ny))
    return sum(max(row) for row in dist)


def b_list_join(n: int) -> int:
    parts: list[str] = []
    for i in range(n):
        parts.append(str(i))
        parts.append(",")
    return len("".join(parts))


def b_dict_items(n: int) -> int:
    d = {str(i): i for i in range(1000)}
    t = 0
    for r in range(n // 1000):
        for k, v in d.items():
            t += v + len(k)
    return t


def b_enumerate_zip(n: int) -> int:
    xs = list(range(1000))
    ys = list(range(1000, 2000))
    t = 0
    for r in range(n // 1000):
        i = 0
        for x, y in zip(xs, ys):
            t += i + x * y
            i += 1
    return t


def b_bytes(n: int) -> int:
    data = bytes(range(256)) * 16
    t = 0
    for r in range(n // len(data)):
        for b in data:
            t += b ^ 0x5A
    return t + data.find(b"\xff\x00") + len(data.replace(b"\x00", b"--"))


def b_in_list(n: int) -> int:
    xs = list(range(100))
    t = 0
    for i in range(n):
        if i % 150 in xs:
            t += 1
    return t


def b_max_key(n: int) -> int:
    xs = [(i * 7919) % 10007 for i in range(1000)]
    t = 0
    for r in range(n // 1000):
        t += max(xs) + min(xs) + sum(xs) + max(xs, key=lambda v: v % 100)
    return t


class Tree:
    def __init__(self, v: int) -> None:
        self.v = v
        self.left: "Tree | None" = None
        self.right: "Tree | None" = None


def insert(t: "Tree | None", v: int) -> Tree:
    if t is None:
        return Tree(v)
    if v < t.v:
        t.left = insert(t.left, v)
    else:
        t.right = insert(t.right, v)
    return t


def depth(t: "Tree | None") -> int:
    if t is None:
        return 0
    return 1 + max(depth(t.left), depth(t.right))


def b_tree(n: int) -> int:
    root: Tree | None = None
    for i in range(n):
        root = insert(root, (i * 7919) % 100003)
    return depth(root)


def make_tree(d: int) -> "Tree":
    t = Tree(d)
    if d > 0:
        t.left = make_tree(d - 1)
        t.right = make_tree(d - 1)
    return t


def count(t: "Tree | None") -> int:
    return 0 if t is None else 1 + count(t.left) + count(t.right)


def b_alloc_tree(n: int) -> int:
    t = 0
    for i in range(n):
        t += count(make_tree(14))
    return t


G = 0


def b_global(n: int) -> int:
    global G
    G = 0
    for i in range(n):
        G += i & 3
    return G


def b_collatz(n: int) -> int:
    best = 0
    for start in range(1, n):
        x = start
        steps = 0
        while x != 1:
            x = x // 2 if x % 2 == 0 else 3 * x + 1
            steps += 1
        if steps > best:
            best = steps
    return best


def b_sieve(n: int) -> int:
    flags = [True] * n
    flags[0] = flags[1] = False
    i = 2
    while i * i < n:
        if flags[i]:
            for j in range(i * i, n, i):
                flags[j] = False
        i += 1
    return sum(1 for f in flags if f)


def b_any_all(n: int) -> int:
    xs = list(range(100))
    t = 0
    for i in range(n // 100):
        if any(x == i % 120 for x in xs):
            t += 1
        if all(x >= 0 for x in xs):
            t += 1
    return t


def b_defaultdict(n: int) -> int:
    d: defaultdict[int, list[int]] = defaultdict(list)
    for i in range(n):
        d[i % 1000].append(i)
    c = Counter([i % 97 for i in range(n)])
    return sum(len(v) for v in d.values()) + c[5] + len(c)


def b_str_cmp(n: int) -> int:
    ws = ["word%05d" % ((i * 7919) % 10007) for i in range(1000)]
    t = 0
    for r in range(n // 1000):
        for i in range(1, len(ws)):
            if ws[i] < ws[i - 1]:
                t += 1
            if ws[i] == ws[i - 1]:
                t += 100
    return t


def b_nested_loops(n: int) -> int:
    t = 0
    for i in range(n):
        for j in range(i % 50):
            if (i + j) % 3 == 0:
                t += j
            elif (i ^ j) & 1:
                t -= 1
    return t


def b_list_slice(n: int) -> int:
    xs = list(range(1000))
    t = 0
    for i in range(n // 100):
        ys = xs[i % 500 : i % 500 + 100]
        t += ys[0] + len(ys)
        zs = ys[::-1]
        t += zs[0]
    return t


def b_str_build_chars(n: int) -> int:
    out: list[str] = []
    for i in range(n):
        out.append(chr(97 + i % 26))
    s = "".join(out)
    t = 0
    for ch in s:
        if ch in "aeiou":
            t += 1
    return t + s.count("z") + len(s.upper())


BENCHES: list[tuple[str, Callable[[], str]]] = [
    ("int_loop", lambda: str(b_int_loop(20000000))),
    ("float_loop", lambda: str(b_float_loop(20000000))),
    ("list_append_pop", lambda: str(b_list_append_pop(5000000))),
    ("list_comp", lambda: str(b_list_comp(10000000))),
    ("dict_str", lambda: str(b_dict_str(2000000))),
    ("dict_int", lambda: str(b_dict_int(5000000))),
    ("dict_tuple", lambda: str(b_dict_tuple(3000000))),
    ("set_ops", lambda: str(b_set_ops(3000000))),
    ("str_concat", lambda: str(b_str_concat(10000000))),
    ("str_join_split", lambda: str(b_str_join_split(2000000))),
    ("fstring", lambda: str(b_fstring(2000000))),
    ("str_index", lambda: str(b_str_index(20000000))),
    ("str_index_unicode", lambda: str(b_str_index_unicode(2000000))),
    ("str_slice", lambda: str(b_str_slice(10000000))),
    ("method_calls", lambda: str(b_method_calls(10000000))),
    ("virtual", lambda: str(b_virtual(20000000))),
    ("closure", lambda: str(b_closure(20000000))),
    ("generators", lambda: str(b_generators(10000000))),
    ("genexp", lambda: str(b_genexp(10000000))),
    ("exceptions", lambda: str(b_exceptions(2000000))),
    ("keyerror", lambda: str(b_keyerror(2000000))),
    ("sort_ints", lambda: str(b_sort_ints(2000000))),
    ("sort_key", lambda: str(b_sort_key(500000))),
    ("sort_str", lambda: str(b_sort_str(500000))),
    ("fib", lambda: str(b_fib(32))),
    ("tuple_ret", lambda: str(b_tuple_ret(20000000))),
    ("dataclass", lambda: str(b_dataclass(1000000))),
    ("union", lambda: str(b_union(20000000))),
    ("str_methods", lambda: str(b_str_methods(1000000))),
    ("int_str", lambda: str(b_int_str(3000000))),
    ("matmul", lambda: str(b_matmul(200))),
    ("deque_heap", lambda: str(b_deque_heap(2000000))),
    ("optional", lambda: str(b_optional(10000000))),
    ("dot", lambda: str(b_dot(50000000))),
    ("bfs", lambda: str(b_bfs(700))),
    ("list_join", lambda: str(b_list_join(3000000))),
    ("dict_items", lambda: str(b_dict_items(10000000))),
    ("enumerate_zip", lambda: str(b_enumerate_zip(10000000))),
    ("bytes", lambda: str(b_bytes(20000000))),
    ("in_list", lambda: str(b_in_list(1000000))),
    ("max_key", lambda: str(b_max_key(5000000))),
    ("tree", lambda: str(b_tree(500000))),
    ("alloc_tree", lambda: str(b_alloc_tree(30))),
    ("global", lambda: str(b_global(20000000))),
    ("collatz", lambda: str(b_collatz(300000))),
    ("sieve", lambda: str(b_sieve(10000000))),
    ("any_all", lambda: str(b_any_all(5000000))),
    ("defaultdict", lambda: str(b_defaultdict(3000000))),
    ("str_cmp", lambda: str(b_str_cmp(10000000))),
    ("nested_loops", lambda: str(b_nested_loops(1000000))),
    ("list_slice", lambda: str(b_list_slice(5000000))),
    ("str_build_chars", lambda: str(b_str_build_chars(5000000))),
]


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    for name, fn in BENCHES:
        if only and only != name:
            continue
        t0 = time.perf_counter()
        r = fn()
        dt = time.perf_counter() - t0
        print(f"{name}\t{dt:.4f}\t{r}")


main()
