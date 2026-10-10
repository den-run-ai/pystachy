import fastmath

print(fastmath.fib(90), fastmath.shout("hi"), fastmath.total([1.0, 2.5]))
try:
    fastmath.fib(91)
except fastmath.TooBig as e:
    print("caught", e)
