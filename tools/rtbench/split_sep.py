t = "a,bb,ccc,dddd," * 10000
n = 0
for i in range(60):
    n += len(t.split(","))
print(n)
