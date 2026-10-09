t = "Hello World " * 10000
n = 0
for i in range(200):
    n += len(t.upper()) + len(t.lower())
print(n)
