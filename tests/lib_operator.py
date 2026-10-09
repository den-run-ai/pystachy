# CPython's own pure-Python Lib/operator.py (lib/operator.py, unmodified): its functions are
# templates, compiled for the argument types of each call
import operator
from operator import add, itemgetter

print(add(2, 3), add("a", "b"), add([1], [2]), add(1.5, 2), operator.mul("ab", 3), operator.mul(3, [0]))
print(operator.sub(10, 4.5), operator.truediv(7, 2), operator.floordiv(-7, 2), operator.mod(-7, 3), operator.mod(7.5, 2), operator.pow(2, 10), operator.pow(2.0, 0.5))
print(operator.and_(12, 10), operator.or_(12, 3), operator.xor(5, 1), operator.lshift(1, 5), operator.rshift(256, 2), operator.inv(5), operator.invert(0), operator.neg(-2.5), operator.pos(3))
print(operator.abs(-3), operator.abs(-2.5), operator.not_(0), operator.not_("x"), operator.truth([0]), operator.truth(""), operator.is_(None, None), operator.is_not(None, None))
print(operator.contains("abc", "b"), operator.contains([1, 2], 3), operator.contains({"k": 1}, "k"), operator.countOf([1, 2, 1, 1], 1), operator.countOf("banana", "a"))
print(operator.indexOf("hello", "l"), operator.indexOf([3, 4, 5], 5), operator.concat("x", "y"), operator.concat([1], [2, 3]))
print(operator.eq("a", "a"), operator.ne(1, 2), operator.ge(2.5, 2), operator.gt("b", "a"), operator.le(1, 1), operator.lt((1, 2), (1, 3)))
xs = [1, 2, 3, 4]
operator.setitem(xs, 0, 9)
operator.delitem(xs, 1)
d = {"a": 1}
operator.setitem(d, "b", 2)
operator.delitem(d, "a")
print(xs, d, operator.getitem(xs, -1), operator.getitem(d, "b"), operator.getitem("abc", 1))
print(operator.iadd([1], [2]), operator.iadd(1, 2), operator.isub(5, 3), operator.imul(3, 4), operator.imul("ab", 2), operator.iconcat("x", "y"), operator.ifloordiv(7, 2), operator.imod(7, 4), operator.ipow(3, 3))
print(operator.iand(6, 3), operator.ior(6, 3), operator.ixor(6, 3), operator.ilshift(1, 3), operator.irshift(16, 2), operator.itruediv(1.0, 4.0))
print(operator.__add__(1, 1), operator.__lt__(1, 2), operator.__not__(True), operator.__getitem__([5, 6], 1), len(operator.__all__))
print(operator.indexOf([1, 2], 5))
