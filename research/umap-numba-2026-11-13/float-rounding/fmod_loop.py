import sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000000
seed = 42.0
acc = 0.0
for k in range(n):
    seed = (seed * 3877.0 + 29573.0) % 139968.0
    acc += seed / 139968.0
q = 0.0
x = -1234.75
for k in range(n // 4):
    q += (x + k) // 7.0 + (x - k) % -3.5
print(seed, acc, q)
