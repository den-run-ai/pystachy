# Retained CPU buffers: native bulk scoring, layout, aliases, and lifetime.
from pyobj import Buffer, import_module, of_float, of_int

f = import_module("cpu_buffer_fixtures")
make = f.attr("make")
source = make.call([of_int(0)])
b = source.buffer_f64(True)
ro = source.buffer_f64()
print("metadata", b.dtype(), b.shape(), b.strides(), b.offset(), b.nbytes(), b.storage_nbytes(), b.readonly(), ro.readonly())
source.close()
print("source closed", b.dot(ro), b.get(-1))
s = b.view(1, 3, 2)
r = s.view(2, 3, -1)
print("views", s.shape(), s.strides(), s.offset(), r.strides(), r.offset(), r.get(0), s.dot(r))
s.set(1, 30.0)
print("alias", b.get(3), ro.get(3), r.get(1))
b.close()
b.close()
print("parent closed", s.get(1), s.dot(r))
empty = r.view(3, 0)
print("empty", len(empty), empty.offset(), empty.nbytes(), empty.storage_nbytes(), empty.dot(empty))
empty.close()
s.close()
r.close()
ro.close()

for case in [7, 8, 9]:
    obj = make.call([of_int(case)])
    view = obj.buffer_f64()
    print("layout", case, view.shape(), view.strides(), view.offset(), view.dot(view))
    view.close()
    obj.close()

for case in [2, 3, 4, 5, 6]:
    obj = make.call([of_int(case)])
    try:
        obj.buffer_f64()
        print("bad layout accepted", case)
    except (TypeError, ValueError) as e:
        print("rejected", case, str(e))
    obj.close()

obj = make.call([of_int(1)])
b = obj.buffer_f64()
print("readonly exporter", b.dot(b))
try:
    obj.buffer_f64(True)
except TypeError as e:
    print("readonly import", str(e))
try:
    b.set(0, 9.0)
except TypeError as e:
    print("readonly write", str(e))
obj.close()

for index in [-7, 6, -9223372036854775808]:
    try:
        b.get(index)
    except IndexError as e:
        print("index", index, str(e))
for start, count, step in [(-1, 1, 1), (7, 0, 1), (6, 1, 1), (0, -1, 1), (0, 2, 0), (0, 2, -1), (5, 2, 1), (0, 1, 9223372036854775807), (0, 9223372036854775807, 2)]:
    try:
        b.view(start, count, step)
    except (ValueError, IndexError, OverflowError) as e:
        print("view rejected", start, count, step, str(e))
short = b.view(0, 1)
try:
    b.dot(short)
except ValueError as e:
    print("dot length", str(e))
short.close()
try:
    b.dot(short)
except ValueError as e:
    print("dot closed", str(e))
b.close()
try:
    b.get(0)
except ValueError as e:
    print("closed", str(e))
try:
    obj.buffer_f64()
except ValueError as e:
    print("closed source", str(e))

# PEP 688 release callbacks prove that the export lasts across calls, pins its
# exporter after closing the original Object, and releases exactly once.
watched = f.attr("watched")
alive = f.attr("alive")
releases = f.attr("releases")
exports = f.attr("exports")
resize = f.attr("resize")
mutate = f.attr("mutate")
obj = watched.call([])
b = obj.buffer_f64()
v = b.view(1, 2)
print("pinned", exports.call([]).to_int(), releases.call([]).to_int(), bool(alive.call([])))
try:
    resize.call([])
except Exception:
    print("resize blocked")
mutate.call([])
print("host alias mutation", b.get(1), v.get(0))
b.close()
obj.close()
print("retained child", bool(alive.call([])), v.dot(v), releases.call([]).to_int())
v.close()
v.close()
print("released", bool(alive.call([])), releases.call([]).to_int())
obj = watched.call([])
b = obj.buffer_f64()
b.close()
resize.call([])
print("resize after release", releases.call([]).to_int())
obj.close()

# Unclosed handles must not leak exports. A function return removes native GC
# stack roots; subsequent tracked allocations trigger collection without gc API.
def drop_buffer() -> None:
    obj = watched.call([])
    local = obj.buffer_f64()
    child = local.view(3, 4, -1)
    assert child.dot(local) == 20.0
    obj.close()

before = releases.call([]).to_int()
for i in range(200):
    drop_buffer()
for i in range(30000):
    of_float(float(i))
print("collected exports", releases.call([]).to_int() - before == 200, not bool(alive.call([])))

# Sequential binary64 multiply/add, including a case that FMA changes.
import math

numeric = f.attr("numeric")
for case in range(8):
    pair = numeric.call([of_int(case)])
    left = pair[of_int(0)].buffer_f64()
    right = pair[of_int(1)].buffer_f64()
    value = left.dot(right)
    if case == 2 or case == 4 or case == 6:
        good = math.isnan(value)
    elif case == 3 or case == 7:
        good = value == float("inf")
    else:
        good = value == 0.0 and math.copysign(1.0, value) == 1.0
    assert good
    print("numeric", case, good)
    left.close()
    right.close()
    pair.close()
obj = make.call([of_int(0)])
root = obj.buffer_f64()
child = root.view(5, 3, -2).view(2, 3, -1)
print("nested permission", child.readonly())
try:
    child.set(0, 12.0)
except TypeError as e:
    print("nested readonly", str(e))
child.close()
root.close()
obj.close()
