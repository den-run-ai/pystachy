from pyobj import import_module, of_int

bg = import_module("bg")
bg.attr("start").call([of_int(1)])
a = bg.attr("count").call([]).to_int()
x = 0
for i in range(300000000):
    x = (x * 31 + i) % 1000003
b = bg.attr("count").call([]).to_int()
bg.attr("halt").call([])
print("background thread progressed during compiled loop:", b - a > 2, x)
