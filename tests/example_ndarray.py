# examples/ndarray: a float64 array in the subset and lazy expressions over it, as CPython computes
# them: views, broadcasting, out= and in-place operators, IEEE division by zero, the summation
# policy (pairwise in NumPy's order, a compensated lazy sum, an ill-conditioned sum), matrix
# products, the checks of shapes and indices, and results recorded from NumPy 2.5.3
from lazy import lazy
from ndarray import (NDArray, add, arange, array, array2, divide, dot, greater, matmul, mean, multiply,
                     pairwise, subtract, sum_axis, total, zeros)


def floats(seed: int, n: int) -> list[float]:
    out: list[float] = []
    s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        out.append((s / 2147483648.0 - 0.5) * 100.0)
    return out


def show(what: str, a: NDArray) -> None:
    print(what, a.shape, a.values())


def same(x: float, y: float) -> bool:
    if x != x or y != y:
        return x != x and y != y
    return x == y and (x != 0.0 or str(x) == str(y))


def numpy(what: str, mine: float, theirs: float) -> None:
    print("numpy", "ok" if same(mine, theirs) else "DIFFERS", what, repr(mine))


a = array2([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
b = array([10.0, 20.0, 30.0])
col = array2([[100.0], [200.0]])
cube = NDArray(floats(1, 24), [2, 3, 4], [12, 4, 1], 0)
show("a + b", a + b)
show("a - col", a - col)
show("a * a", a * a)
show("a / b", a / b)
show("a * 2.5", a * 2.5)
show("a - 1", a - 1)
show("-a", -a)
show("a.T", a.T)
show("a.T * a.T", a.T * a.T)
show("-a.T", -(a.T))
show("cube + a.row(0) as (3,1)", cube + a.row(0).reshape([3, 1]))
show("cube.T + 1", cube.T + 1.0)
show("cube.row(1)", cube.row(1))
show("cube.row(-1).row(2)", cube.row(-1).row(2))
show("a.reshape([3, 2])", a.reshape([3, 2]))
show("a.T.reshape([6])", a.T.reshape([6]))
show("cube.reshape([4, -1])", cube.reshape([4, -1]))
show("arange(-3)", arange(-3))
show("zeros([2, 0])", zeros([2, 0]))
z = zeros([3, 1])
print("reshape of a (1, 3) transpose is a view:", z.T.reshape([3]).data is z.data, z.T.contiguous())
print(a.contiguous(), a.T.contiguous(), a.ndim, a.size, len(a), a[1, 2], a[-1, -3], b[2], b[-3], cube[1, 2, 3])
special = array([1.0, -1.0, 0.0, -0.0, float("inf"), float("-inf"), float("nan"), 2.5])
show("special / 0.0", special / 0.0)
show("special / -0.0", special / -0.0)
show("special / special", special / special)
show("special * special", special * special)
t = a.T
t[2, 1] = 60.0
print("t[2, 1] = 60:", a[1, 2], repr(a))

out = zeros([2, 3])
print("add into out:", add(a, b, out) is out, out.values())
show("multiply into out", multiply(a, 2.0, out))
show("divide into out", divide(a, col, out))
c = a.copy()
c += b
c *= 2.0
c -= col
c /= 4
show("+= *= -= /=", c)
sq = NDArray([float(i) for i in range(9)], [3, 3], [3, 1], 0)
show("add(sq, sq.T, out=sq)", add(sq, sq.T, sq))
v = arange(5)
subtract(v, v, v)
show("subtract(v, v, out=v)", v)

m = NDArray(floats(2, 35), [5, 7], [7, 1], 0)
for x in [m, m.T, cube.row(0)]:
    print("total", repr(total(x)), "mean", repr(mean(x)))
    show("sum axis 0", sum_axis(x, 0))
    show("sum axis 1", sum_axis(x, 1))
    show("sum axis -1", sum_axis(x, -1))
for n in [0, 1, 7, 8, 9, 127, 128, 129, 1000]:
    xs = floats(n + 3, n)
    print("total", n, repr(total(array(xs))), repr(mean(array(xs))) if n else "-")
print(repr(total(array([-0.0]))), repr(total(array([-0.0, -0.0]))), repr(mean(zeros([0]))))
view = cube.T.row(1)
print("a 2-D view sums its C-order items:", total(view) == 0.0 + pairwise(view.values(), 0, view.size, 1))
u = array(floats(4, 50))
w = array(floats(5, 50))
print("dot", repr(dot(u, w)), repr(total(u * w)))
p = NDArray(floats(6, 12), [3, 4], [4, 1], 0)
q = NDArray(floats(7, 20), [4, 5], [5, 1], 0)
show("p @ q", p @ q)
show("matmul(q.T, p.T)", matmul(q.T, p.T))
print(greater(a, 3.0), greater(a.T, 3.0))

x = array(floats(8, 300))
y = array(floats(9, 300))
d = lazy(x) - lazy(y)
print("lazy sum", repr((d * d).sum()), repr(sum(((x - y) * (x - y)).values())), repr(total((x - y) * (x - y))))
print("lazy evaluate", (lazy(x) * lazy(y) + 1.0).evaluate().values() == (x * y + 1.0).values())
print("lazy divide", ((lazy(x) - 2) / lazy(y)).evaluate().values() == ((x - 2) / y).values())
into = x.copy()
expected = (into * y + into).values()
print("lazy evaluate into an operand", (lazy(into) * lazy(y) + lazy(into)).evaluate(into).values() == expected)
later = lazy(b) + lazy(b)
b.data[0] = 1.0
show("lazy reads the array when evaluated", later.evaluate())
show("a copy of a view is a whole array", (lazy(a.T.row(1).copy()) * 2.0).evaluate())
canc = array([1e16] + [1.0] * 100 + [-1e16])
print("ill-conditioned: total", repr(total(canc)), "lazy sum", repr((lazy(canc) + 0.0).sum()),
      "sum()", repr(sum(canc.values())))

big = array(floats(10, 1000))
numpy("np.sum(big)", total(big), -238.95645793527365)
numpy("np.mean(big)", mean(big), -0.23895645793527365)
numpy("np.sum(m.T)", total(m.T), 105.57712744921446)
numpy("np.sum(m, axis=0)[3]", sum_axis(m, 0)[3], 85.16473975032568)
numpy("np.sum(m.T, axis=1)[3]", sum_axis(m.T, 1)[3], 85.16473975032568)
numpy("np.sum(m, axis=1)[2]", sum_axis(m, 1)[2], -174.76817332208157)
numpy("np.sum(cube.T)", total(cube.T), -28.742973320186138)
numpy("np.sum(canc)", total(canc), 84.0)
numpy("np.sum((x - y) * (x - y))", total((x - y) * (x - y)), 499245.4202189208)
numpy("((x - 2) / y)[17]", ((x - 2) / y)[17], -0.5537008075689765)
numpy("(cube + m[0, :4])[1, 2, 3]", (cube + array(m.row(0).values()[:4]))[1, 2, 3], -29.120803298428655)
numpy("np.divide(-1.0, -0.0)", (array([-1.0]) / -0.0)[0], float("inf"))

for k in range(22):
    try:
        if k == 0:
            print(a + array([1.0, 2.0]))
        elif k == 1:
            print(a * col.T)
        elif k == 2:
            print(a.reshape([4]))
        elif k == 3:
            print(a.reshape([4, -1]))
        elif k == 4:
            print(a.reshape([-1, -1]))
        elif k == 5:
            print(zeros([-1, -2]))
        elif k == 6:
            print(a[2, 0])
        elif k == 7:
            print(a[0, -4])
        elif k == 8:
            print(a[0, 0, 99])
        elif k == 9:
            print(b[3])
        elif k == 10:
            print(b[0, 0])
        elif k == 11:
            print(a[0])
        elif k == 12:
            print(zeros([]).row(0))
        elif k == 13:
            print(add(a, a, zeros([3])))
        elif k == 14:
            print(add(b, a, b))
        elif k == 15:
            print(matmul(a, a))
        elif k == 16:
            print(dot(b, array([1.0])))
        elif k == 17:
            print(sum_axis(a, 2))
        elif k == 18:
            print(lazy(a))
        elif k == 19:
            print(lazy(a.row(1)))
        elif k == 20:
            print(lazy(b) + lazy(array([1.0])))
        else:
            print(len(NDArray([1.0], [], [], 0)))
    except (ValueError, IndexError, TypeError) as e:
        print(type(e).__name__, repr(str(e)))
