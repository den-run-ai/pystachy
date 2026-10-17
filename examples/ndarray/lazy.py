"""lazy: elementwise expressions over whole 1-D NDArrays that compile to one loop.

usage: from lazy import lazy
       d = lazy(a) - lazy(b)
       (d * d).sum()                          # sum((a - b) * (a - b)), without temporaries
       (lazy(a) * lazy(b) + 1.0).evaluate()   # a new NDArray, made in one pass

An operator on lazy(...) operands or numbers returns a Node, whose class is specialized for its
operands' types and its operation (_node is a template, and so is every Node's __init__). An
expression's at() is therefore a nest of direct calls that LLVM inlines into one loop: the fusion
numexpr gets from a run-time virtual machine, and Eigen from C++ expression templates.

Operands are whole 1-D arrays (NDArray.whole()) of one length, or numbers. Their items are read
when the expression is evaluated, not when it is built, so a change to an operand in between shows
in the result. lazy() rejects a view of part of an array or a strided one: lazy(a.copy()) takes a
snapshot of it instead.

evaluate() computes each item by the same IEEE operations as the eager expression (Pystachy never
contracts a * b + c into a fused multiply-add), so the two arrays are equal. sum() adds the items as
Python's sum() of floats does: in order, with Neumaier's compensation, which keeps the error from
growing with the number of items. np.sum and total() add pairwise without compensation, so for
ill-conditioned sums the results differ (README.md).
"""
import math

from ndarray import NDArray, true_divide


def _add(x: float, y: float) -> float:
    return x + y


def _sub(x: float, y: float) -> float:
    return x - y


def _mul(x: float, y: float) -> float:
    return x * y


class Leaf:
    # an array operand: its list, read at evaluation. Loops run to len(self.data), which lets LLVM
    # drop the bounds checks of data[i] (with a length kept in a field instead, the same sum took
    # 1.7 times as long)
    def __init__(self, a: NDArray) -> None:
        if a.ndim != 1:
            raise ValueError(f"lazy() takes a 1-D array, not a {a.ndim}-D one")
        if not a.whole():
            raise ValueError("lazy() takes a whole array, not a view of part of one: use lazy(a.copy())")
        self.data: list[float] = a.data

    def at(self, i: int) -> float:
        return self.data[i]

    def size(self) -> int:
        return len(self.data)

    def __add__(self, other):
        return _node(self, _operand(other), _add)

    def __sub__(self, other):
        return _node(self, _operand(other), _sub)

    def __mul__(self, other):
        return _node(self, _operand(other), _mul)

    def __truediv__(self, other):
        return _node(self, _operand(other), true_divide)


class Scalar:
    # a number operand, the same at every index; its size, -1, fits any length
    def __init__(self, v: float) -> None:
        self.v = v

    def at(self, i: int) -> float:
        return self.v

    def size(self) -> int:
        return -1


class Node:
    def __init__(self, left, right, op) -> None:
        m = left.size()
        k = right.size()
        if m >= 0 and k >= 0 and m != k:
            raise ValueError(f"operands could not be broadcast together with shapes ({m},) ({k},) ")
        self.left = left
        self.right = right
        self.op = op

    def at(self, i: int) -> float:
        return self.op(self.left.at(i), self.right.at(i))

    def size(self) -> int:
        # a Leaf's or a Node's: a Scalar is only ever the right operand
        return self.left.size()

    def __add__(self, other):
        return _node(self, _operand(other), _add)

    def __sub__(self, other):
        return _node(self, _operand(other), _sub)

    def __mul__(self, other):
        return _node(self, _operand(other), _mul)

    def __truediv__(self, other):
        return _node(self, _operand(other), true_divide)

    def evaluate(self, out: NDArray | None = None) -> NDArray:
        # the items in one pass, into a new array or into out (which may be one of the operands:
        # item i of each is read before item i of out is written). One loop calls at(): LLVM
        # inlines a method called from one place, not from several
        n = self.size()
        if out is None:
            res = NDArray([0.0] * n, [n], [1], 0)
        elif out.shape != [n] or not out.contiguous():
            raise ValueError(f"out must be a contiguous array of shape ({n},)")
        else:
            res = out
        od = res.data
        oo = res.offset
        for i in range(n):
            od[oo + i] = self.at(i)
        return res

    def sum(self) -> float:
        # Python's sum() of the items (CPython 3.12+'s, which Pystachy's runtime also has): in order
        # with Neumaier's compensation, the compensation added last. Python adds the first item to 0
        # plainly; the compensated step from 0.0 gives the same sum, with one call of at()
        s = 0.0
        c = 0.0
        for i in range(self.size()):
            x = self.at(i)
            t = s + x
            c += (s - t) + x if abs(s) >= abs(x) else (x - t) + s
            s = t
        return s + c if c != 0.0 and math.isfinite(c) else s


def lazy(a: NDArray) -> Leaf:
    return Leaf(a)


def _node(left, right, op):
    # a module-level template, so that each call builds the specialization of Node for its argument
    # types (inside Node's methods, Node would name the current specialization)
    return Node(left, right, op)


def _operand(v):
    # a template: a number becomes a Scalar, an expression stays as it is (arrays need lazy(): a
    # test of isinstance(v, NDArray) would not be decided at compile time, since an object may be None)
    if isinstance(v, float) or isinstance(v, int):
        return Scalar(float(v))
    return v
