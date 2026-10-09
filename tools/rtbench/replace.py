t = "the cat sat on the mat " * 5000
n = 0
for i in range(100):
    n += len(t.replace("at", "og"))
print(n)
