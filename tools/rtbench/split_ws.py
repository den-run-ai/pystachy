t = "lorem ipsum  dolor\tsit amet consectetur " * 5000
n = 0
for i in range(60):
    n += len(t.split())
print(n)
